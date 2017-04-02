"""
Script to generate and upload a signing key to keyservers
"""
from __future__ import print_function

import argparse
import sys

from django.core.management.base import LabelCommand
from django.utils.translation import ugettext as _

from email_extras.models import Key
from email_extras.settings import SIGNING_KEY_DATA
from email_extras.utils import get_gpg


gpg = get_gpg()


# Create an action that *extends* a list, instead of *appending* to it
class ExtendAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        items = getattr(namespace, self.dest) or []
        items.extend(values)
        setattr(namespace, self.dest, items)


class Command(LabelCommand):
    label = "FINGERPRINT"
    missing_args_message = ("Enter at least one fingerprint or use the "
                            "--generate option.")

    def add_arguments(self, parser):
        # Register our extending action
        parser.register('action', 'extend', ExtendAction)

        parser.add_argument('args', metavar=self.label, nargs='*')
        parser.add_argument(
            '--generate',
            action='store_true',
            default=False,
            help=_("Generate a new signing key"))
        parser.add_argument(
            '--print-private-key',
            action='store_true',
            default=False,
            dest='print_private_key',
            help=_("Print the private signing key"))
        parser.add_argument(
            '-k', '--keyserver',
            # We want multiple uses of -k server1 server 2 -k server3 server4
            # to be interpreted as [server1, server2, server3, server4], so we
            # need to use the custom ExtendAction we defiend before
            action='extend',
            nargs='+',
            dest='keyservers',
            help=_("Upload (the most recently generated) public signing key "
                   "to the specified keyservers"))

    def handle(self, *labels, **options):
        # EITHER specify the key fingerprints OR generate a key
        if options.get('generate') and labels:
            print("You cannot specify fingerprints and --generate when "
                  "running this command")
            sys.exit(-1)

        if options.get('generate'):
            signing_key_cmd = gpg.gen_key_input(**SIGNING_KEY_DATA)
            new_signing_key = gpg.gen_key(signing_key_cmd)

            exported_signing_key = gpg.export_keys(
                new_signing_key.fingerprint)

            self.key = Key.objects.create(key=exported_signing_key,
                                          use_asc=False)
            labels = [self.key.fingerprint]

        return super(Command, self).handle(*labels, **options)

    def handle_label(self, label, **options):
        try:
            self.key = Key.objects.get(fingerprint=label)
        except Key.DoesNotExist:
            print("Key matching fingerprint '%(fp)s' not found." % {
                'fp': label,
            })
            sys.exit(-1)

        for ks in set(options.get('keyservers')):
            gpg.send_keys(ks, self.key.fingerprint)

        output = ''

        if options.get('print_private_key'):
            output += gpg.export_keys([self.key.fingerprint], True)

        # If we havne't been told to do anything else, print out the public
        # signing key
        if not options.get('keyservers') and \
           not options.get('print_private_key'):
            output += gpg.export_keys([self.key.fingerprint])

        return output
