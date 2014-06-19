# Core
import os
import sys
import shutil
import tempfile
import functools
import contextlib
from glob import glob
from datetime import datetime
from importlib import import_module

# 3rd Party
import nose
import mongoengine
from click import echo
from pymongo import MongoClient
from nose.tools import with_setup
from click.testing import CliRunner
from nose.plugins.skip import SkipTest

# Local
from monarch import cli, create_migration_directory_if_necessary

mongo_port = int(os.environ.get('MONARCH_MONGO_DB_PORT', 27017))

TEST_ENVIRONEMNTS = {
    'test': {
        'db_name': 'test_monarch',
        'host': 'localhost',
        'port': mongo_port
    },
    'from_test': {
        'db_name': 'from_monarch_test',
        'host': 'localhost',
        'port': mongo_port
    },
    'to_test': {
        'db_name': 'to_monarch_test',
        'host': 'localhost',
        'port': mongo_port
    },
}

BACKUPS = {
    'LOCAL': {
        'backup_dir': 'path_to_backups',
    },
}

TEST_CONFIG = """
# monarch settings file, generated by monarch init
# feal free to edit it with your application specific settings

ENVIRONMENTS = {}

BACKUPS = {}

""".format(TEST_ENVIRONEMNTS, BACKUPS)

TEST_MIGRATION = """
from monarch import MongoBackedMigration

class {migration_class_name}(MongoBackedMigration):

    def run(self):
        print("running a migration with no failure")
"""

TEST_FAILED_MIGRATION = """
from monarch import MongoBackedMigration

class {migration_class_name}(MongoBackedMigration):

    def run(self):
        print("running a migration with failure")
        raise Exception('Yikes we messed up the database -- oh nooooooooo')
"""


def no_op():
    pass


@contextlib.contextmanager
def isolated_filesystem_with_path():
    """A context manager that creates a temporary folder and changes
    the current working directory to it for isolated filesystem tests.

    The modification here is that it adds itself to the path

    """
    cwd = os.getcwd()
    t = tempfile.mkdtemp()
    os.chdir(t)
    sys.path.insert(1, t)
    try:
        yield t
    finally:
        os.chdir(cwd)
        sys.path.remove(t)
        try:
            shutil.rmtree(t)
        except (OSError, IOError):
            pass


def requires_mongoengine(func):
    @functools.wraps(func)
    def wrapper(*args, **kw):
        if mongoengine is None:
            raise SkipTest("mongoengine is not installed")
        return func(*args, **kw)

    return wrapper


def clear_mongo_databases():
    for env_name in TEST_ENVIRONEMNTS:
        env = TEST_ENVIRONEMNTS[env_name]
        client = MongoClient(host=env['host'], port=env['port'])
        client.drop_database(env['db_name'])


def initialize_monarch(working_dir, backup_dir=None):
    migration_path = os.path.join(os.path.abspath(working_dir), 'migrations')
    create_migration_directory_if_necessary(migration_path)
    settings_file = os.path.join(os.path.abspath(working_dir), 'migrations/settings.py')
    with open(settings_file, 'w') as f:
        if backup_dir:
            f.write(TEST_CONFIG.replace('path_to_backups', backup_dir))
        else:
            f.write(TEST_CONFIG)

    m = import_module('migrations')
    reload(m)
    s = import_module('migrations.settings')
    reload(s)


def ensure_current_migrations_module_is_loaded():
    # everytime within the same python process we add migrations we need to reload the migrations module
    # for it could be cached from a previous test
    m = import_module('migrations')
    reload(m)


def test_create_migration():
    runner = CliRunner()
    with isolated_filesystem_with_path() as working_dir:
        initialize_monarch(working_dir)
        result = runner.invoke(cli, ['generate', 'add_indexes'])
        new_files_generated = glob(working_dir + '/*/*migration.py')
        assert len(new_files_generated) == 1
        file_name = new_files_generated[0]
        assert 'add_indexes_migration.py' in file_name
        assert os.path.getsize(file_name) > 0
        assert result.exit_code == 0


def test_initialization():
    runner = CliRunner()
    with isolated_filesystem_with_path() as working_dir:
        result = runner.invoke(cli, ['init'])
        settings_file = os.path.join(working_dir, 'migrations/settings.py')
        assert os.path.getsize(settings_file) > 0
        assert result.exit_code == 0


def first_migration(working_dir):
    new_files_generated = glob(working_dir + '/*/*migration.py')
    assert len(new_files_generated) == 1
    return new_files_generated[0]


def register_connections():
    s = import_module('migrations.settings')
    for env_name in s.ENVIRONMENTS:
        env = s.ENVIRONMENTS[env_name]
        mongoengine.register_connection(env_name, env['db_name'], port=env['port'])


def establish_connection(env_name):
    s = import_module('migrations.settings')
    env = s.ENVIRONMENTS[env_name]
    mongoengine.connect(env['db_name'], port=env['port'])


def get_db(env):
    client = MongoClient(host=env['host'], port=env['port'])
    return client[env['db_name']]


@requires_mongoengine
@with_setup(no_op, clear_mongo_databases)
def test_run_migration():
    runner = CliRunner()
    with isolated_filesystem_with_path() as cwd:
        initialize_monarch(cwd)
        runner.invoke(cli, ['generate', 'add_column_to_user_table'])

        # Update Migration Template with a *proper* migration
        current_migration = first_migration(cwd)
        class_name = "{}Migration".format('AddColumnToUserTable')
        with open(current_migration, 'w') as f:
            f.write(TEST_MIGRATION.format(migration_class_name=class_name))

        ensure_current_migrations_module_is_loaded()

        result = runner.invoke(cli, ['migrate', 'test'])
        # echo('output: {}'.format(result.output))
        # echo('exception: {}'.format(result.exception))
        assert result.exit_code == 0


@requires_mongoengine
@with_setup(no_op, clear_mongo_databases)
def test_failed_migration():
    runner = CliRunner()
    with isolated_filesystem_with_path() as cwd:
        initialize_monarch(cwd)
        result = runner.invoke(cli, ['generate', 'add_account_table'])
        # echo('output: {}'.format(result.output))
        # echo('exception: {}'.format(result.exception))

        # Update Migration Template with a *proper* migration
        current_migration = first_migration(cwd)
        class_name = "{}Migration".format('AddAccountTable')
        with open(current_migration, 'w') as f:
            f.write(TEST_FAILED_MIGRATION.format(migration_class_name=class_name))

        ensure_current_migrations_module_is_loaded()

        result = runner.invoke(cli, ['migrate', 'test'])
        # echo('output: {}'.format(result.output))
        # echo('exception: {}'.format(result.exception))
        assert result.exit_code == -1


def populate_database(env_name):
    from_db = get_db(TEST_ENVIRONEMNTS[env_name])
    from_fishes = from_db.fishes
    fish = {'name': "Red Fish"}
    from_fishes.insert(fish)
    assert from_fishes.count() == 1


@requires_mongoengine
@with_setup(no_op, clear_mongo_databases)
def test_copy_db():
    runner = CliRunner()
    with isolated_filesystem_with_path() as cwd:
        initialize_monarch(cwd)

        populate_database('from_test')

        to_db = get_db(TEST_ENVIRONEMNTS['to_test'])
        to_fishes = to_db.fishes

        assert to_fishes.count() == 0

        result = runner.invoke(cli, ['copy_db', 'from_test:to_test'], input="y\ny\n")

        assert to_fishes.count() == 1


@requires_mongoengine
@with_setup(no_op, clear_mongo_databases)
def test_list_migrations():
    runner = CliRunner()

    with isolated_filesystem_with_path() as working_dir:
        initialize_monarch(working_dir)
        for migration_name in ['add_indexes', 'add_user_table', 'add_account_table']:
            runner.invoke(cli, ['generate', migration_name])

        ensure_current_migrations_module_is_loaded()

        result = runner.invoke(cli, ['list_migrations', 'test'])

        assert result.exit_code == 0


@requires_mongoengine
@with_setup(no_op, clear_mongo_databases)
def test_backup_database():
    runner = CliRunner()
    with isolated_filesystem_with_path() as working_dir:
        backup_dir = os.path.join(working_dir, 'backups')
        os.mkdir(backup_dir)

        initialize_monarch(working_dir, backup_dir=backup_dir)
        populate_database('from_test')

        result = runner.invoke(cli, ['backup', 'from_test'])

        assert result.exit_code == 0
        assert len([name for name in os.listdir(backup_dir)]) == 1

@requires_mongoengine
@with_setup(no_op, clear_mongo_databases)
def test_list_backups():
    runner = CliRunner()
    with isolated_filesystem_with_path() as working_dir:
        backup_dir = os.path.join(working_dir, 'backups')
        os.mkdir(backup_dir)

        initialize_monarch(working_dir, backup_dir=backup_dir)
        populate_database('from_test')

        runner.invoke(cli, ['backup', 'from_test'])
        runner.invoke(cli, ['backup', 'from_test'])

        result = runner.invoke(cli, ['list_backups'])

        echo('tlb output: {}'.format(result.output))
        echo('tlb exception: {}'.format(result.exception))

        assert result.exit_code == 0
        assert "from_monarch_test__{}.dmp.zip".format(datetime.utcnow().strftime("%Y_%m_%d")) in result.output
        assert "from_monarch_test__{}_2.dmp.zip".format(datetime.utcnow().strftime("%Y_%m_%d")) in result.output


@requires_mongoengine
@with_setup(no_op, clear_mongo_databases)
def test_restore_database():
    runner = CliRunner()
    with isolated_filesystem_with_path() as working_dir:
        backup_dir = os.path.join(working_dir, 'backups')
        os.mkdir(backup_dir)

        initialize_monarch(working_dir, backup_dir=backup_dir)
        populate_database('from_test')

        result = runner.invoke(cli, ['backup', 'from_test'])
        echo('trd_a output: {}'.format(result.output))
        echo('trd_a exception: {}'.format(result.exception))
        assert result.exit_code == 0

        migration_name = "from_monarch_test__{}.dmp.zip".format(datetime.utcnow().strftime("%Y_%m_%d"))
        result = runner.invoke(cli, ['restore', "{}:to_test".format(migration_name)], input="y\ny\n")
        echo('trd_b output: {}'.format(result.output))
        echo('trd_b exception: {}'.format(result.exception))
        assert result.exit_code == 0

        # Check to see if the database that was imported has the right data
        to_db = get_db(TEST_ENVIRONEMNTS['to_test'])
        to_fishes = to_db.fishes
        assert to_fishes.count() == 1





if __name__ == "__main__":
    nose.run()
