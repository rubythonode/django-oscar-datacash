from decimal import Decimal as D
from xml.dom.minidom import parseString
import datetime
import math
import time
from mock import Mock
from unittest import skipUnless

from django.test import TestCase
from django.conf import settings

from datacash.models import OrderTransaction
from datacash.gateway import Gateway
from oscar.apps.payment.utils import Bankcard


SAMPLE_REQUEST = """<?xml version="1.0" encoding="UTF-8" ?>
<Request>
    <Authentication>
        <client>99000001</client>
        <password>boomboom</password>
    </Authentication>
    <Transaction>
    <CardTxn>
        <Card>
            <pan>1000011100000004</pan>
            <expirydate>04/06</expirydate>
            <startdate>01/04</startdate>
        </Card>
        <method>auth</method>
    </CardTxn>
    <TxnDetails>
        <merchantreference>1000001</merchantreference>
        <amount currency="GBP">95.99</amount>
    </TxnDetails>
    </Transaction>
</Request>"""

SAMPLE_RESPONSE = """<?xml version="1.0" encoding="UTF-8" ?>
<Response>
    <CardTxn>
        <authcode>060642</authcode>
        <card_scheme>Switch</card_scheme>
        <country>United Kingdom</country>
        <issuer>HSBC</issuer>
    </CardTxn>
    <datacash_reference>3000000088888888</datacash_reference>
    <merchantreference>1000001</merchantreference>
    <mode>LIVE</mode>
    <reason>ACCEPTED</reason>
    <status>1</status>
    <time>1071567305</time>
</Response>"""


class TransactionModelTests(TestCase):
    
    def test_cc_numbers_are_not_saved_in_xml(self):
        txn = OrderTransaction.objects.create(order_number='1000',
                                              method='auth',
                                              datacash_ref='3000000088888888',
                                              merchant_ref='1000001',
                                              amount=D('95.99'),
                                              status=1,
                                              reason='ACCEPTED',
                                              request_xml=SAMPLE_REQUEST,
                                              response_xml=SAMPLE_RESPONSE)
        doc = parseString(txn.request_xml)
        element = doc.getElementsByTagName('pan')[0]
        self.assertEqual('XXXXXXXXXXXX0004', element.firstChild.data)


class GatewayMockTests(TestCase):

    def setUp(self):
        self.gateway = Gateway('example.com', 'dummyclient', 'dummypassword')

    def test_successful_auth(self):
        response_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <CardTxn>
        <authcode>100000</authcode>
        <card_scheme>Mastercard</card_scheme>
        <country>United Kingdom</country>
    </CardTxn>
    <datacash_reference>4000203021904745</datacash_reference>
    <merchantreference>TEST_132473839018</merchantreference>
    <mode>TEST</mode>
    <reason>ACCEPTED</reason>
    <status>1</status>
    <time>1324738433</time>
</Response>"""
        self.gateway.do_request = Mock(return_value=response_xml)
        response = self.gateway.auth(amount=D('1000.00'),
                                     currency='GBP',
                                     card_number='1000350000000007',
                                     expiry_date='10/12',
                                     merchant_reference='TEST_132473839018')
        self.assertEquals(1, response['status'])
        self.assertEquals('TEST_132473839018', response['merchant_reference'])
        self.assertEquals('ACCEPTED', response['reason'])
        self.assertEquals('100000', response['auth_code'])
        self.assertEquals('Mastercard', response['card_scheme'])
        self.assertEquals('United Kingdom', response['country'])


@skipUnless(hasattr(settings, 'DATACASH_CLIENT'), "No integration credentials provided")
class GatewayIntegrationTests(TestCase):

    def setUp(self):
        self.gateway = Gateway(settings.DATACASH_HOST,
                               settings.DATACASH_CLIENT,
                               settings.DATACASH_PASSWORD)

    def generate_merchant_reference(self):
        return 'TEST_%s' % int(math.floor(time.time() * 100))

    def test_successful_auth(self):
        # Using test card from Datacash's docs
        ref = self.generate_merchant_reference()
        response = self.gateway.auth(amount=D('1000.00'),
                                     currency='GBP',
                                     card_number='1000350000000007',
                                     expiry_date='10/12',
                                     merchant_reference=ref)
        self.assertEquals(1, response['status'])
        self.assertEquals(ref, response['merchant_reference'])
        self.assertEquals('ACCEPTED', response['reason'])
        self.assertEquals('100000', response['auth_code'])
        self.assertEquals('Mastercard', response['card_scheme'])
        self.assertEquals('United Kingdom', response['country'])