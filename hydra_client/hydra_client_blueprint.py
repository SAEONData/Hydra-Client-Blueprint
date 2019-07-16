from uuid import uuid4

from flask import flash, redirect, url_for, session, request
from flask_login import current_user, login_user, logout_user
from flask_dance.consumer import OAuth2ConsumerBlueprint, oauth_authorized, oauth_error
from flask_dance.consumer.storage.sqla import SQLAlchemyStorage
from flask.helpers import get_env
from sqlalchemy.orm.exc import NoResultFound


class HydraClientBlueprint(OAuth2ConsumerBlueprint):
    """
    Blueprint for setting up a client application to use ORY Hydra as an OAuth2 / OpenID Connect
    provider. Encapsulates :class:`OAuth2ConsumerBlueprint`, and adds logout capabilities.

    Provides the following routes:

    ``/login``
        initiates a login with Hydra
    ``/authorized``
        callback from Hydra after successful authentication & authorization
    ``/logout``
        initiates a logout with Hydra
    ``/logged_out``
        callback from Hydra after successful logout
    """

    def __init__(self, name, import_name, db, user_model, token_model):
        """
        :param db: Flask-SQLAlchemy database object
        :param user_model: User model class;
            this should be a flask_login.UserMixin or similar
        :param token_model: Token model class;
            this should be a hydra_client.HydraTokenMixin or similar
        """
        super().__init__(
            name,
            import_name,
            login_url='/login',
            authorized_url='/authorized',
            scope=['openid'],
            storage=SQLAlchemyStorage(token_model, db.session, user=current_user),

            # hack to disable SSL certificate verification in a dev environment:
            # this is a sneaky way to make flask-dance set the 'verify' kwarg for
            # requests calls made when fetching tokens; it's not the intended use
            # of token_url_params, but hey-ho
            token_url_params={'verify': get_env() != 'development'},
        )

        self.db = db
        self.user_model = user_model
        self.token_model = token_model

        self.hydra_public_url = None
        self.userinfo_url = None
        self.logout_url = None

        self.from_config['hydra_public_url'] = 'HYDRA_PUBLIC_URL'
        self.from_config['client_id'] = 'HYDRA_CLIENT_ID'
        self.from_config['client_secret'] = 'HYDRA_CLIENT_SECRET'

        self.add_url_rule('/logout', view_func=self.logout)
        self.add_url_rule('/logged_out', view_func=self.logged_out)

        oauth_authorized.connect(self.hydra_logged_in, sender=self)
        oauth_error.connect(self.hydra_error, sender=self)

        self.create_local_user = None

    def load_config(self):
        super().load_config()
        self.authorization_url = self.hydra_public_url + '/oauth2/auth'
        self.token_url = self.hydra_public_url + '/oauth2/token'
        self.userinfo_url = self.hydra_public_url + '/userinfo'
        self.logout_url = self.hydra_public_url + '/oauth2/sessions/logout'

    def local_user_creator(self, callback):
        """
        Use as a decorator to set a callback for automatically creating a local user,
        if required, upon successful authentication with Hydra.
        The function should take a userinfo (a ``dict`` originating from the Hydra
        userinfo endpoint) and return a user object.

        For example:
        ::
            @blueprint.local_user_creator
            def create_local_user(userinfo):
                return User(id=userinfo['sub'], email=userinfo['email'])
        """
        self.create_local_user = callback
        return callback

    def hydra_logged_in(self, bp, token):
        """
        Log the user in locally on successful Hydra login.
        """
        assert self == bp

        if not token:
            flash("Unable to log in.", category='error')
            return False

        r = self.session.get(self.userinfo_url)
        if not r.ok:
            flash("Unable to fetch user info.", category='error')
            return False

        userinfo = r.json()
        user_id = userinfo['sub']

        # find or create the OAuth token in the DB
        try:
            local_token = self.token_model.query.filter_by(provider=self.name, user_id=user_id).one()
        except NoResultFound:
            local_token = self.token_model(provider=self.name, user_id=user_id, token=token)

        if not local_token.user:
            # associate the user with the token
            user = self.user_model.query.get(user_id)
            if not user:
                if self.create_local_user:
                    user = self.create_local_user(userinfo)
                else:
                    flash("User not found.", category='error')
                    return False

            local_token.user = user
            self.db.session.add(local_token)
            self.db.session.commit()

        login_user(local_token.user)
        flash("Logged in.")

        # disable Flask-Dance's default behavior for saving the OAuth token
        return False

    def hydra_error(self, bp, **kwargs):
        """
        Notify on Hydra error.
        """
        assert self == bp

        msg = "OAuth error from {name}: error={error} error_description={error_description}".format(
            name=self.name.title(),
            error=kwargs.pop('error', ''),
            error_description=kwargs.pop('error_description', ''),
        )
        flash(msg, category='error')

    def logout(self):
        """
        Initiate a logout from Hydra.
        """
        local_token = self.token_model.query.filter_by(provider=self.name, user_id=current_user.id).one()
        state_key = "{bp.name}_oauth_state".format(bp=self)
        state_val = str(uuid4())
        session[state_key] = state_val
        logged_out_url = url_for('.logged_out', _external=True)

        url = '{hydra_logout_url}?id_token_hint={id_token}&post_logout_redirect_uri={post_logout_redirect_uri}&state={state}'.format(
            hydra_logout_url=self.logout_url,
            post_logout_redirect_uri=logged_out_url,
            id_token=local_token.token['id_token'],
            state=state_val,
        )
        return redirect(url)

    def logged_out(self):
        """
        Log the user out locally on successful Hydra logout.
        """
        state_key = "{bp.name}_oauth_state".format(bp=self)
        state_val = request.args.get('state')
        if state_key in session and session[state_key] == state_val:
            logout_user()
            del session[state_key]
            flash("Logged out.")
        return redirect('/')
