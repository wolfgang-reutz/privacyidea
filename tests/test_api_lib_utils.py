# -*- coding: utf-8 -*-
"""
This tests the file api.lib.utils
"""
from .base import MyApiTestCase

from privacyidea.api.lib.utils import (getParam,
                                       check_policy_name,
                                       verify_auth_token, is_fqdn, attestation_certificate_allowed,
                                       get_priority_from_param)
from privacyidea.lib.error import ParameterError
import jwt
import mock
import datetime
import warnings
from privacyidea.lib.error import AuthError


class UtilsTestCase(MyApiTestCase):

    def test_01_getParam(self):
        s = getParam({"serial": ""}, "serial", optional=False, allow_empty=True)
        self.assertEqual(s, "")

        self.assertRaises(ParameterError, getParam, {"serial": ""}, "serial", optional=False, allow_empty=False)

        # check for allowed values
        v = getParam({"sslverify": "0"}, "sslverify", allowed_values=["0", "1"], default="1")
        self.assertEqual("0", v)

        v = getParam({"sslverify": "rogue value"}, "sslverify", allowed_values=["0", "1"], default="1")
        self.assertEqual("1", v)

        v = getParam({}, "sslverify", allowed_values=["0", "1"], default="1")
        self.assertEqual("1", v)

    def test_02_check_policy_name(self):
        check_policy_name("This is a new valid Name")
        check_policy_name("THis-is-a-valid-Name")
        # The name "check" is reserved
        self.assertRaises(ParameterError, check_policy_name, "check")
        # This is an invalid name
        self.assertRaises(ParameterError, check_policy_name, "~invalid name")

        # some disallowed patterns:
        self.assertRaises(ParameterError, check_policy_name, "Check")
        self.assertRaises(ParameterError, check_policy_name, "pi-update-policy-something")
        # Some patterns that work
        check_policy_name("check this out.")
        check_policy_name("my own pi-update-policy-something")
        check_policy_name("pi-update-policysomething")

    def test_03_verify_auth_token(self):
        # create a jwt with a trusted private key
        with open("tests/testdata/jwt_sign.key", "r") as f:
            key = f.read()

        # successful authentication with wildcard user, starting with an "h" and ending with "s"
        auth_token = jwt.encode(payload={"role": "user",
                                         "username": "hans",
                                         "realm": "realmX",
                                         "resolver": "resolverX"},
                                key=key,
                                algorithm="RS256")
        r = verify_auth_token(auth_token=auth_token,
                              required_role="user")
        self.assertEqual(r.get("realm"), "realmX")
        self.assertEqual(r.get("username"), "hans")
        self.assertEqual(r.get("resolver"), "resolverX", )
        self.assertEqual(r.get("role"), "user")

        # A user starting with hans and ending with "t" is not allowed
        auth_token = jwt.encode(payload={"role": "user",
                                         "username": "hanswurst",
                                         "realm": "realmX",
                                         "resolver": "resolverX"},
                                key=key,
                                algorithm="RS256")
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', category=DeprecationWarning)
            self.assertRaisesRegexp(
                AuthError,
                "The username hanswurst is not allowed to impersonate via JWT.",
                verify_auth_token, auth_token=auth_token, required_role="user")

        # A user ending with hans is not allowed
        # A user starting with hans and ending with "t" is not allowed
        auth_token = jwt.encode(payload={"role": "user",
                                         "username": "kleinerhans",
                                         "realm": "realmX",
                                         "resolver": "resolverX"},
                                key=key,
                                algorithm="RS256")
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', category=DeprecationWarning)
            self.assertRaisesRegexp(
                AuthError,
                "The username kleinerhans is not allowed to impersonate via JWT.",
                verify_auth_token, auth_token=auth_token, required_role="user")

        # Successful authentication with dedicated user
        with mock.patch("logging.Logger.warning") as mock_log:
            auth_token = jwt.encode(payload={"role": "user",
                                             "username": "userA",
                                             "realm": "realm1",
                                             "resolver": "resolverX"},
                                    key=key,
                                    algorithm="RS256")
            r = verify_auth_token(auth_token=auth_token,
                                  required_role="user")
            self.assertEqual(r.get("realm"), "realm1")
            self.assertEqual(r.get("username"), "userA")
            self.assertEqual(r.get("resolver"), "resolverX",)
            self.assertEqual(r.get("role"), "user")
            # ...but there is an unsupported configuration
            mock_log.assert_called_once_with("Unsupported JWT algorithm in PI_TRUSTED_JWT.")

        # The signature has expired
        expired_token = jwt.encode(payload={"role": "admin",
                                            "exp": datetime.datetime.utcnow()-datetime.timedelta(seconds=1000)},
                                   key=key,
                                   algorithm="RS256")
        self.assertRaises(AuthError, verify_auth_token, auth_token=expired_token, required_role="admin")

        # The signature does not match
        with mock.patch("logging.Logger.info") as mock_log:
            auth_token = jwt.encode(payload={"role": "user",
                                             "username": "userA",
                                             "realm": "realm1",
                                             "resolver": "resolverX"},
                                    key=key,
                                    algorithm="RS256")
            r = verify_auth_token(auth_token=auth_token,
                                  required_role="user")
            mock_log.assert_any_call("A given JWT definition does not match.")

    def test_04_check_jwt_username_in_audit(self):
        # Here we check, if the username from the trusted JWT appears in the audit log.
        # This means that the username is read in the correct way from the JWT and
        # also used in the correct way for policy handling.
        with open("tests/testdata/jwt_sign.key", "r") as f:
            key = f.read()

        auth_token = jwt.encode(payload={"role": "user", "username": "userA", "realm": "realm1",
                                         "resolver": "resolverX"},
                                key=key,
                                algorithm="RS256")

        # The authenticated but non-existing user tries for fetch his tokens
        with self.app.test_request_context('/token/',
                                           method='GET',
                                           headers={"Authorization": auth_token}):
            res = self.app.full_dispatch_request()
            self.assertTrue(res.status_code == 400, res)

        # We see the user from the trusted JWT in the audit log.
        ae = self.find_most_recent_audit_entry(action="GET /token/")
        self.assertEqual(ae.get("user"), u"userA")

    def test_05_is_fqdn(self):
        self.assertTrue(is_fqdn('example.com'))
        self.assertFalse(is_fqdn('https://example.com'))

    def test_06_attestation_certificate_allowed(self):
        # No policies, return True.
        self.assertTrue(attestation_certificate_allowed(None, None))
        self.assertTrue(attestation_certificate_allowed({}, {}))

        # Policy but no info, return False.
        self.assertFalse(attestation_certificate_allowed(None, {"subject/.*Yubico.*/": ['WebAuthn']}))
        self.assertFalse(attestation_certificate_allowed({}, {"subject/.*Yubico.*/": ['WebAuthn']}))

        # Certificate allowed, return True.
        self.assertTrue(attestation_certificate_allowed({"attestation_subject": "C=SE,O=Yubico AB"},
                                                        {"subject/.*Yubico.*/": ['WebAuthn']}))

        # Certificate not allowed, return False.
        self.assertFalse(attestation_certificate_allowed({"attestation_subject": "C=SE,O=Frobnicate"},
                                                         {"subject/.*Yubico.*/": ['WebAuthn']}))

        # Multiple Policies, match iff all match.
        self.assertTrue(
            attestation_certificate_allowed(
                {
                    "attestation_subject": "C=SE,O=Yubico AB",
                    "attestation_serial": "61730834"
                },
                {
                    "subject/.*Yubico.*/": ['WebAuthn1'],
                    "serial/61730834/": ['WebAuthn2']
                }
            )
        )
        self.assertFalse(
            attestation_certificate_allowed(
                {
                    "attestation_subject": "C=SE,O=Yubico AB",
                    "attestation_serial": "61730834"
                },
                {
                    "subject/.*Yubico.*/": ['WebAuthn1'],
                    "serial/12345678/": ['WebAuthn2']
                }
            )
        )

    def test_07_get_priority_from_param(self):
        # check if only keys with given integer values are returned
        param = {'priority.resolver1': 1, 'priority.resolver2': None,
                 'resolvers': 'resolver1,resolver2,resolver3'}
        priority = get_priority_from_param(param)
        self.assertEqual(priority, {'resolver1': 1})
