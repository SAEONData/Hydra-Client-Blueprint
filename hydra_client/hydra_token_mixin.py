from flask_dance.consumer.storage.sqla import OAuthConsumerMixin
from sqlalchemy import Column, String, ForeignKey, UniqueConstraint
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import relationship


class HydraTokenMixin(OAuthConsumerMixin):
    """
    A SQLAlchemy declarative mixin for defining a model that stores the OAuth token
    obtained from ORY Hydra for an authenticated user.

    Provides columns defined by :class:`OAuthConsumerMixin`, as well as:

    ``user_id``
        foreign key to the user model id column
    ``user``
        relationship to the user model
    """

    # override Flask-Dance's table name and provider column definitions
    __tablename__ = 'hydra_token'
    __table_args__ = (UniqueConstraint('provider', 'user_id'),)
    provider = Column(String, nullable=False, index=True)

    @declared_attr
    def user_id(cls):
        return Column(String, ForeignKey(cls.user_id_column(), ondelete='CASCADE'), nullable=False)

    @declared_attr
    def user(cls):
        return relationship(cls.user_model_name())

    @classmethod
    def user_id_column(cls):
        return 'user.id'

    @classmethod
    def user_model_name(cls):
        return 'User'
