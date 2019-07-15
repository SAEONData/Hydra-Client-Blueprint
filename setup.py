from setuptools import setup, find_packages

version = '0.1.0'

setup(
    name='Hydra-Client-Blueprint',
    version=version,
    description='A Flask blueprint that enables OAuth2 / OpenID Connect authentication via ORY Hydra',
    url='https://github.com/SAEONData/Hydra-Client-Blueprint',
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
