from betfairlightweight import APIClient
import os
import keyring


# Change this certs path to wherever you're storing your certificates
certs_path = os.environ['USERPROFILE'] + r'\OneDrive\Betfair\bf certs'

my_username = keyring.get_password('bf_username', 'joel')
my_password = keyring.get_password('bf_password', 'joel')
my_app_key = keyring.get_password('bf_app_key',  'joel')


def get_api_client() -> APIClient:
    """Get Betfair API client with credentials"""
    return APIClient(
        username=my_username,
        password=my_password,
        app_key=my_app_key,
        certs=certs_path)
