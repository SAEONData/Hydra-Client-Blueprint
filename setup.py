from setuptools import setup, find_packages

version = '0.2.0'

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
    install_requires=[
        # use requirements.txt
    ],
    python_requires='~=3.6',
)
