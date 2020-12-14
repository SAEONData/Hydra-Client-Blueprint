# Hydra-OAuth2-Blueprint

***This library has been superseded by the hydra_oauth2 lib module in the Open-Data-Platform project.***

A [Flask](https://palletsprojects.com/p/flask/) blueprint for setting up an application as an OAuth2
client of an [ORY Hydra](https://www.ory.sh/docs/hydra/) server. Encapsulates the `OAuth2ConsumerBlueprint`
class provided by [Flask-Dance](https://flask-dance.readthedocs.io/en/latest/index.html), and adds signup
and logout capabilities.

The logout capability is supported inherently by Hydra, while signup is an OAuth2 login with a custom
"mode" parameter tacked onto the authorization URL. As such, a canonical login provider implementation
integrated with Hydra would simply handle a signup request as a login.

The [ODP Identity](https://github.com/SAEONData/ODP-Identity) service, which integrates with Hydra
as login, consent and logout provider, recognizes this mode parameter, carrying out a signup or login
as applicable. Upon completion of either signup or login, the user will be authenticated and the client
application will receive an OAuth2 token.

## Installation

Requires Python 3.6

The package should be installed into the same virtual environment as the application.

## Configuration

The blueprint is configured through the standard Flask config API. The following options are available:

- **`HYDRA_PUBLIC_URL`**: URL of the Hydra public API
- **`OAUTH2_CLIENT_ID`**: client ID of the application as registered with Hydra
- **`OAUTH2_CLIENT_SECRET`**: client secret of the application as registered with Hydra
- **`OAUTH2_SCOPES`**: a whitespace-separated list of OAuth2 scopes for which issued tokens will be valid;
  should include `openid` if ID tokens / user info is required
- **`OAUTH2_AUDIENCE`**: (optional) OAuth2 audience for which issued tokens will be valid

### Environment variables

If running the application locally (or otherwise) on HTTP, then the following environment variable
should be set. _N.B. This should be used in development only._

- `OAUTHLIB_INSECURE_TRANSPORT`: set to `True` to allow OAuth2 to work over HTTP (default `False`)
