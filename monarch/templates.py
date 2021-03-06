MIGRATION_TEMPLATE = '''
from monarch import echo
from monarch import {base_class}

# Optionally
# from monarch import progressbar
#
# Usage:
# with progressbar(all_the_users_to_process,
#                  label='Modifying user accounts',
#                  length=number_of_users) as bar:
#    for user in bar:
#        modify_the_user(user)
#
#
# Note: Using echos (or prints) will mess up the way this looks
#
# More info: http://click.pocoo.org/utils/#showing-progress-bars


class {migration_class_name}({base_class}):

    def run(self):
        """Write the code here that will migrate the database from one state to the next
            No Need to handle exceptions -- we will take care of that for you
        """
        raise NotImplementedError


'''

QUERYSET_TEMPLATE = '''
from click import prompt
from monarch import {base_class}


class {queryset_class_name}({base_class}):

    def run(self):
        """Write the code here that will perform the mongo dump of the collections that you care about
        """
        raise NotImplementedError


'''

CONFIG_TEMPLATE = """
# monarch settings file, generated by monarch init
# feal free to edit it with your application specific settings

ENVIRONMENTS = {
    'production': {
        'host': 'your-host:12345,your-other-host:12347',
        'db_name': 'your-db-name',
        'username': 'asdf',
        'password': 'asdfdf',
        'sslCAFile': '/path/to/production.pem'
    },
    'development': {
        'host': 'your-host:12345',
        'db_name': 'your-db-name',
        'username': 'asdf',
        'password': 'asdfdf'
    },
}


# If you want to use the backups feature uncomment and fill out the following:
# BACKUPS = {
#     'S3': {
#         'bucket_name': 'your_bucket_name',
#         'aws_access_key_id': 'aws_access_key_id',
#         'aws_secret_access_key': 'aws_secret_access_key',
#     }
# }

# OR

# BACKUPS = {
#     'LOCAL': {
#         'backup_dir': 'path_to_backups',
#     }
# }


"""