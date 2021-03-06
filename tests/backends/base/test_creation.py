import copy
from unittest import mock

from django.db import DEFAULT_DB_ALIAS, connection, connections
from django.db.backends.base.creation import (
    TEST_DATABASE_PREFIX, BaseDatabaseCreation,
)
from django.test import SimpleTestCase

from ..models import Object, ObjectReference


def get_connection_copy():
    # Get a copy of the default connection. (Can't use django.db.connection
    # because it'll modify the default connection itself.)
    test_connection = copy.copy(connections[DEFAULT_DB_ALIAS])
    test_connection.settings_dict = copy.deepcopy(
        connections[DEFAULT_DB_ALIAS].settings_dict
    )
    return test_connection


class TestDbSignatureTests(SimpleTestCase):
    def test_default_name(self):
        # A test db name isn't set.
        prod_name = 'hodor'
        test_connection = get_connection_copy()
        test_connection.settings_dict['NAME'] = prod_name
        test_connection.settings_dict['TEST'] = {'NAME': None}
        signature = BaseDatabaseCreation(test_connection).test_db_signature()
        self.assertEqual(signature[3], TEST_DATABASE_PREFIX + prod_name)

    def test_custom_test_name(self):
        # A regular test db name is set.
        test_name = 'hodor'
        test_connection = get_connection_copy()
        test_connection.settings_dict['TEST'] = {'NAME': test_name}
        signature = BaseDatabaseCreation(test_connection).test_db_signature()
        self.assertEqual(signature[3], test_name)

    def test_custom_test_name_with_test_prefix(self):
        # A test db name prefixed with TEST_DATABASE_PREFIX is set.
        test_name = TEST_DATABASE_PREFIX + 'hodor'
        test_connection = get_connection_copy()
        test_connection.settings_dict['TEST'] = {'NAME': test_name}
        signature = BaseDatabaseCreation(test_connection).test_db_signature()
        self.assertEqual(signature[3], test_name)


@mock.patch.object(connection, 'ensure_connection')
@mock.patch('django.core.management.commands.migrate.Command.handle', return_value=None)
class TestDbCreationTests(SimpleTestCase):
    def test_migrate_test_setting_false(self, mocked_migrate, mocked_ensure_connection):
        test_connection = get_connection_copy()
        test_connection.settings_dict['TEST']['MIGRATE'] = False
        creation = test_connection.creation_class(test_connection)
        old_database_name = test_connection.settings_dict['NAME']
        try:
            with mock.patch.object(creation, '_create_test_db'):
                creation.create_test_db(verbosity=0, autoclobber=True, serialize=False)
            mocked_migrate.assert_not_called()
        finally:
            with mock.patch.object(creation, '_destroy_test_db'):
                creation.destroy_test_db(old_database_name, verbosity=0)

    def test_migrate_test_setting_true(self, mocked_migrate, mocked_ensure_connection):
        test_connection = get_connection_copy()
        test_connection.settings_dict['TEST']['MIGRATE'] = True
        creation = test_connection.creation_class(test_connection)
        old_database_name = test_connection.settings_dict['NAME']
        try:
            with mock.patch.object(creation, '_create_test_db'):
                creation.create_test_db(verbosity=0, autoclobber=True, serialize=False)
            mocked_migrate.assert_called_once()
        finally:
            with mock.patch.object(creation, '_destroy_test_db'):
                creation.destroy_test_db(old_database_name, verbosity=0)


class TestDeserializeDbFromString(SimpleTestCase):
    databases = {'default'}

    def test_circular_reference(self):
        # deserialize_db_from_string() handles circular references.
        data = """
        [
            {
                "model": "backends.object",
                "pk": 1,
                "fields": {"obj_ref": 1, "related_objects": []}
            },
            {
                "model": "backends.objectreference",
                "pk": 1,
                "fields": {"obj": 1}
            }
        ]
        """
        connection.creation.deserialize_db_from_string(data)
        obj = Object.objects.get()
        obj_ref = ObjectReference.objects.get()
        self.assertEqual(obj.obj_ref, obj_ref)
        self.assertEqual(obj_ref.obj, obj)
