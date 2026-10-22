import unittest,socket,tempfile
from pathlib import Path
from scripts.select_port import choose
from scripts.check_nginx_domain import check
class RoutingTests(unittest.TestCase):
 def test_occupied_port_is_skipped_without_disrupting_owner(self):
  with socket.socket() as sock:
   sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
   selected=choose(port,start=20000,end=20100)
   self.assertNotEqual(selected,port);self.assertEqual(sock.getsockname()[1],port)
 def test_shared_and_duplicate_site_files_are_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   site=Path(tmp)/'digi';site.write_text('server {server_name digi.example credit.example;}')
   with self.assertRaises(ValueError):check('digi.example',site,'')
   site.write_text('server {server_name digi.example;}')
   with self.assertRaises(ValueError):check('digi.example',site,'# configuration file /other/site:\nserver {server_name digi.example;}\n')
   check('digi.example',site,'# configuration file '+str(site)+':\nserver {server_name digi.example;}\n')
