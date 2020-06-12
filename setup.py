from setuptools import setup, find_packages

version = '1.0.0'

setup(
    name='Hydra-OAuth2-Blueprint',
    version=version,
    description='A Flask blueprint that enables OAuth2 / OpenID Connect authentication via ORY Hydra',
    url='https://github.com/SAEONData/Hydra-OAuth2-Blueprint',
    author='Mark Jacobson',
    author_email='mark@saeon.ac.za',
    license='MIT',
    packages=find_packages(),
    include_package_data=True,
    python_requires='~=3.6',
    install_requires=[
        'flask',
        'flask-dance[sqla]',
        'flask-login',
        'sqlalchemy',
        'blinker',
    ],
    extras_require={
        'test': ['pytest', 'coverage']
    },
)
