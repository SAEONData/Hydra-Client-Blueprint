from uuid import uuid4
from enum import Enum

from flask import flash, redirect, url_for, session, request
from flask_login import current_user, login_user, logout_user
from flask_dance.consumer import OAuth2ConsumerBlueprint, oauth_authorized, oauth_error
from flask_dance.consumer.storage.sqla import SQLAlchemyStorage
from flask.helpers import get_env
from sqlalchemy.orm.exc import NoResultFound


class LoginMode(Enum):
    LOGIN = 'login'
    SIGNUP = 'signup'


class HydraOAuth2Blueprint(OAuth2ConsumerBlueprint):
    """
    Blueprint for setting up a client application to use ORY Hydra as an OAuth2 / OpenID Connect
    provider. Encapsulates :class:`OAuth2ConsumerBlueprint`, and adds signup and logout capabilities.

    Provides the following routes:

    ``/login``
        initiates a login with Hydra
    ``/signup``
        initiates a signup via Hydra login
    ``/authorized``
        callback from Hydra after successful authentication & authorization
    ``/logout``
        initiates a logout with Hydra
    ``/logged_out``
        callback from Hydra after successful logout
    """

    def __init__(self, name, import_name, db_session, user_model, token_model):
        """
        :param db_session: SQLAlchemy session object
        :param user_model: User model class;
            this should be a flask_login.UserMixin or similar
        :param token_model: Token model class;
            this should be a hydra_oauth2.HydraTokenMixin or similar
        """
        super().__init__(
            name,
            import_name,
            login_url='/login',
            authorized_url='/authorized',
            storage=SQLAlchemyStorage(token_model, db_session, user=current_user),

            # hack to disable SSL certificate verification in a dev environment:
            # this is a sneaky way to make flask-dance set the 'verify' kwarg for
            # requests calls made when fetching tokens; it's not the intended use
            # of token_url_params, but hey-ho
            token_url_params={'verify': get_env() != 'development'},
        )

        self.db_session = db_session
        self.user_model = user_model
        self.token_model = token_model

        self.hydra_public_url = None
        self.userinfo_url = None
        self.logout_url = None

        self.from_config['hydra_public_url'] = 'HYDRA_PUBLIC_URL'
        self.from_config['client_id'] = 'OAUTH2_CLIENT_ID'
        self.from_config['client_secret'] = 'OAUTH2_CLIENT_SECRET'
        self.from_config['scope'] = 'OAUTH2_SCOPES'
        self.from_config['audience'] = 'OAUTH2_AUDIENCE'

        self.add_url_rule('/signup', view_func=self.signup)
        self.add_url_rule('/logout', view_func=self.logout)
        self.add_url_rule('/logged_out', view_func=self.logged_out)

        oauth_authorized.connect(self.hydra_logged_in, sender=self)
        oauth_error.connect(self.hydra_error, sender=self)

        self.create_or_update_local_user = None

    def load_config(self):
        super().load_config()
        self.authorization_url = self.hydra_public_url + '/oauth2/auth'
        self.authorization_url_params = {'audience': getattr(self, 'audience', '')}
        self.token_url = self.hydra_public_url + '/oauth2/token'
        self.userinfo_url = self.hydra_public_url + '/userinfo'
        self.logout_url = self.hydra_public_url + '/oauth2/sessions/logout'

    def local_user_updater(self, callback):
        """
        Use as a decorator to set a callback for automatically creating or updating
        a local user object, if required, after successful authentication with Hydra.
        The function should take a user object (``None`` if creating) and userinfo
        (a ``dict`` originating from the Hydra userinfo endpoint), and should return
        the new or updated user object.

        For example:
        ::
            @blueprint.local_user_updater
            def create_or_update_local_user(user, userinfo):
                if not user:
                    user = User(id=userinfo['sub'])
                user.email = userinfo['email']
                return user
        """
        self.create_or_update_local_user = callback
        return callback

    def _set_login_mode(self, mode: LoginMode):
        self.authorization_url_params['mode'] = mode.value

    def signup(self):
        self._set_login_mode(LoginMode.SIGNUP)
        return super().login()

    def login(self):
        self._set_login_mode(LoginMode.LOGIN)
        return super().login()

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

        # find / create / update the local user object
        local_user = self.db_session.query(self.user_model).get(user_id)
        if self.create_or_update_local_user:
            local_user = self.create_or_update_local_user(local_user, userinfo)
            self.db_session.add(local_user)

        if not local_user:
            flash("User not found.", category='error')
            return False

        # find / create / update the OAuth token
        try:
            local_token = self.db_session.query(self.token_model).filter_by(provider=self.name, user_id=user_id).one()
        except NoResultFound:
            local_token = self.token_model(provider=self.name, user_id=user_id)

        local_token.token = token
        self.db_session.add(local_token)
        self.db_session.commit()

        login_user(local_token.user)
        flash("Logged in.")

        # disable Flask-Dance's default behavior for saving the OAuth token
        return False

    def hydra_error(self, bp, **kwargs):
        """
        Notify on Hydra error.
        """
        assert self == bp

        msg = "OAuth error from {name}: error={error}; error_description={error_description}".format(
            name=self.name.title(),
            error=kwargs.pop('error', ''),
            error_description=kwargs.pop('error_description', ''),
        )
        flash(msg, category='error')

    def logout(self):
        """
        Initiate a logout from Hydra.
        """
        local_token = self.db_session.query(self.token_model).filter_by(provider=self.name, user_id=current_user.id).one()
        state_key = "{bp.name}_oauth_state".format(bp=self)
        state_val = str(uuid4())
        session[state_key] = state_val
        logged_out_url = url_for('.logged_out', _external=True)

        url = '{hydra_logout_url}?id_token_hint={id_token}&post_logout_redirect_uri={post_logout_redirect_uri}&state={state}'.format(
            hydra_logout_url=self.logout_url,
            post_logout_redirect_uri=logged_out_url,
            id_token=local_token.token.get('id_token', ''),
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

    def get_access_token(self):
        """
        Get the logged in user's access token.
        :return: str
        """
        local_token = self.db_session.query(self.token_model).filter_by(provider=self.name, user_id=current_user.id).one()
        return local_token.token['access_token']
