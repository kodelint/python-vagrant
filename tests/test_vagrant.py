'''
Introduces setup and teardown routines suitable for testing Vagrant.

Note that the tests can take few minutes to run because of the time
required to bring up/down the VM.

Most test functions (decorated with `@with_setup`) will actually bring the VM
up/down. This is the "proper" way of doing things (isolation).  However, the
downside of such a workflow is that it increases the execution time of the test
suite.

Before the first test a base box is added to Vagrant under the name
TEST_BOX_NAME. This box is not deleted after the test suite runs in order
to avoid downloading of the box file on every run.
'''

from __future__ import print_function
import os
import re
import unittest
import shutil
import subprocess
import sys
import tempfile
import time
from nose.tools import eq_, ok_, with_setup

import vagrant
from vagrant import compat

# location of a test file on the created box by provisioning in vm_Vagrantfile
TEST_FILE_PATH = '/home/vagrant/python_vagrant_test_file'
# location of Vagrantfiles used for testing.
MULTIVM_VAGRANTFILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   'vagrantfiles', 'multivm_Vagrantfile')
VM_VAGRANTFILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   'vagrantfiles', 'vm_Vagrantfile')
SHELL_PROVISION_VAGRANTFILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'vagrantfiles', 'shell_provision_Vagrantfile')
# the names of the vms from the multi-vm Vagrantfile.
VM_1 = 'web'
VM_2 = 'db'
# name of the base box used for testing
TEST_BOX_NAME = "python-vagrant-base"
# url of the box file used for testing
TEST_BOX_URL = "http://files.vagrantup.com/lucid32.box"
# temp dir for testing.
TD = None



def list_box_names():
    '''
    Return a list of the currently installed vagrant box names.  This is 
    implemented outside of `vagrant.Vagrant`, so that it will still work
    even if the `Vagrant.box_list()` implementation is broken.
    '''
    listing = compat.decode(subprocess.check_output('vagrant box list --machine-readable', shell=True))
    box_names = []
    for line in listing.splitlines():
        # Vagrant 1.8 added additional fields to the --machine-readable output,
        # so unpack the fields according to the number of separators found.
        if line.count(',') == 3:
            timestamp, _, kind, data = line.split(',')
        else:
            timestamp, _, kind, data, extra_data = line.split(',')
        if kind == 'box-name':
            box_names.append(data.strip())
    return box_names


# MODULE-LEVEL SETUP AND TEARDOWN

def setup():
    '''
    Creates the directory used for testing and sets up the base box if not
    already set up.

    Creates a directory in a temporary location and checks if there is a base
    box under the `TEST_BOX_NAME`. If not, downloads it from `TEST_BOX_URL` and
    adds to Vagrant.

    This is ran once before the first test (global setup).
    '''
    sys.stderr.write('module setup()\n')
    global TD
    TD = tempfile.mkdtemp()
    sys.stderr.write('test temp dir: {}\n'.format(TD))
    boxes = list_box_names()
    if TEST_BOX_NAME not in boxes:
        cmd = 'vagrant box add {} {}'.format(TEST_BOX_NAME, TEST_BOX_URL)
        subprocess.check_call(cmd, shell=True)


def teardown():
    '''
    Removes the directory created in setup.

    This is run once after the last test.
    '''
    sys.stderr.write('module teardown()\n')
    if TD is not None:
        shutil.rmtree(TD)


# TEST-LEVEL SETUP AND TEARDOWN

def make_setup_vm(vagrantfile=None):
    '''
    Make and return a function that sets up the temporary directory with a
    Vagrantfile.  By default, use VM_VAGRANTFILE.
    vagrantfile: path to a vagrantfile to use as Vagrantfile in the testing temporary directory.
    '''
    if vagrantfile is None:
        vagrantfile = VM_VAGRANTFILE

    def setup_vm():
        shutil.copy(vagrantfile, os.path.join(TD, 'Vagrantfile'))

    return setup_vm


def teardown_vm():
    '''
    Attempts to destroy every VM in the Vagrantfile in the temporary directory, TD.
    It is not an error if a VM has already been destroyed.
    '''
    try:
        # Try to destroy any vagrant box that might be running.
        subprocess.check_call('vagrant destroy -f', cwd=TD, shell=True)
    except subprocess.CalledProcessError:
        pass
    finally:
        # remove Vagrantfile created by setup.
        os.unlink(os.path.join(TD, "Vagrantfile"))



@with_setup(make_setup_vm(), teardown_vm)
def test_parse_plugin_list():
    '''
    Test the parsing the output of the `vagrant plugin list` command.
    '''
    # listing should match output generated by `vagrant plugin list`.
    listing = '''1424145521,,plugin-name,sahara
1424145521,sahara,plugin-version,0.0.16
1424145521,,plugin-name,vagrant-share
1424145521,vagrant-share,plugin-version,1.1.3%!(VAGRANT_COMMA) system
'''
    # Can compare tuples to Plugin class b/c Plugin is a collections.namedtuple.
    goal = [('sahara', '0.0.16', False), ('vagrant-share', '1.1.3', True)]
    v = vagrant.Vagrant(TD)
    parsed = v._parse_plugin_list(listing)
    assert goal == parsed, 'The parsing of the test listing did not match the goal.\nlisting={!r}\ngoal={!r}\nparsed_listing={!r}'.format(listing, goal, parsed)


@with_setup(make_setup_vm(), teardown_vm)
def test_parse_box_list():
    '''
    Test the parsing the output of the `vagrant box list` command.
    '''
    listing = '''1424141572,,box-name,precise64
1424141572,,box-provider,virtualbox
1424141572,,box-version,0
1424141572,,box-name,python-vagrant-base
1424141572,,box-provider,virtualbox
1424141572,,box-version,0
'''
    # Can compare tuples to Box class b/c Box is a collections.namedtuple.
    goal = [('precise64', 'virtualbox', '0'),
            ('python-vagrant-base', 'virtualbox', '0')]
    v = vagrant.Vagrant(TD)
    parsed = v._parse_box_list(listing)
    assert goal == parsed, 'The parsing of the test listing did not match the goal.\nlisting={!r}\ngoal={!r}\nparsed_listing={!r}'.format(listing, goal, parsed)


@with_setup(make_setup_vm(), teardown_vm)
def test_parse_status():
    '''
    Test the parsing the output of the `vagrant status` command.
    '''
    listing = '''1424098924,web,provider-name,virtualbox
1424098924,web,state,running
1424098924,web,state-human-short,running
1424098924,web,state-human-long,The VM is running. To stop this VM%!(VAGRANT_COMMA) you can run `vagrant halt` to\\nshut it down forcefully%!(VAGRANT_COMMA) or you can run `vagrant suspend` to simply\\nsuspend the virtual machine. In either case%!(VAGRANT_COMMA) to restart it again%!(VAGRANT_COMMA)\\nsimply run `vagrant up`.
1424098924,db,provider-name,virtualbox
1424098924,db,state,not_created
1424098924,db,state-human-short,not created
1424098924,db,state-human-long,The environment has not yet been created. Run `vagrant up` to\\ncreate the environment. If a machine is not created%!(VAGRANT_COMMA) only the\\ndefault provider will be shown. So if a provider is not listed%!(VAGRANT_COMMA)\\nthen the machine is not created for that environment.
'''
    # Can compare tuples to Status class b/c Status is a collections.namedtuple.
    goal = [('web', 'running', 'virtualbox'),
            ('db', 'not_created', 'virtualbox')]
    v = vagrant.Vagrant(TD)
    parsed = v._parse_status(listing)
    assert goal == parsed, 'The parsing of the test listing did not match the goal.\nlisting={!r}\ngoal={!r}\nparsed_listing={!r}'.format(listing, goal, parsed)


@with_setup(make_setup_vm(), teardown_vm)
def test_vm_status():
    '''
    Test whether vagrant.status() correctly reports state of the VM, in a
    single-VM environment.
    '''
    v = vagrant.Vagrant(TD)
    assert v.NOT_CREATED == v.status()[0].state, "Before going up status should be vagrant.NOT_CREATED"
    command = 'vagrant up'
    subprocess.check_call(command, cwd=TD, shell=True)
    assert v.RUNNING in v.status()[0].state, "After going up status should be vagrant.RUNNING"

    command = 'vagrant halt'
    subprocess.check_call(command, cwd=TD, shell=True)
    assert v.POWEROFF in v.status()[0].state, "After halting status should be vagrant.POWEROFF"

    command = 'vagrant destroy -f'
    subprocess.check_call(command, cwd=TD, shell=True)
    assert v.NOT_CREATED in v.status()[0].state, "After destroying status should be vagrant.NOT_CREATED"


@with_setup(make_setup_vm(), teardown_vm)
def test_vm_lifecycle():
    '''
    Test methods controlling the VM - init(), up(), halt(), destroy().
    '''

    v = vagrant.Vagrant(TD)

    # Test init by removing Vagrantfile, since v.init() will create one.
    os.unlink(os.path.join(TD, 'Vagrantfile'))
    v.init(TEST_BOX_NAME)
    assert v.NOT_CREATED == v.status()[0].state

    v.up()
    assert v.RUNNING == v.status()[0].state

    v.suspend()
    assert v.SAVED == v.status()[0].state

    v.halt()
    assert v.POWEROFF == v.status()[0].state

    v.destroy()
    assert v.NOT_CREATED == v.status()[0].state


@with_setup(make_setup_vm(), teardown_vm)
def test_vm_config():
    '''
    Test methods retrieving ssh config settings, like user, hostname, and port.
    '''
    v = vagrant.Vagrant(TD)
    v.up()
    command = "vagrant ssh-config"
    ssh_config = compat.decode(subprocess.check_output(command, cwd=TD, shell=True))
    parsed_config = dict(line.strip().split(None, 1) for line in
                            ssh_config.splitlines() if line.strip() and not
                            line.strip().startswith('#'))

    user = v.user()
    expected_user = parsed_config["User"]
    eq_(user, expected_user)

    hostname = v.hostname()
    expected_hostname = parsed_config["HostName"]
    eq_(hostname, expected_hostname)

    port = v.port()
    expected_port = parsed_config["Port"]
    eq_(port, expected_port)

    user_hostname = v.user_hostname()
    eq_(user_hostname, "{}@{}".format(expected_user, expected_hostname))

    user_hostname_port = v.user_hostname_port()
    eq_(user_hostname_port,
        "{}@{}:{}".format(expected_user, expected_hostname, expected_port))

    keyfile = v.keyfile()
    try:
        eq_(keyfile, parsed_config["IdentityFile"])
    except AssertionError:
        # Vagrant 1.8 adds quotes around the filepath for the private key.
        eq_(keyfile, parsed_config["IdentityFile"].lstrip('"').rstrip('"'))


@with_setup(make_setup_vm(), teardown_vm)
def test_vm_sandbox_mode():
    '''
    Test methods for enabling/disabling the sandbox mode
    and committing/rolling back changes.

    This depends on the Sahara plugin.
    '''
    # Only test Sahara if it is installed.
    # This leaves the testing of Sahara to people who care.
    sahara_installed = _plugin_installed(vagrant.Vagrant(TD), 'sahara')
    if not sahara_installed:
        return

    v = vagrant.SandboxVagrant(TD)

    sandbox_status = v.sandbox_status()
    assert sandbox_status == "unknown", "Before the VM goes up the status should be 'unknown', " + "got:'{}'".format(sandbox_status)

    v.up()
    sandbox_status = v.sandbox_status()
    assert sandbox_status == "off", "After the VM goes up the status should be 'off', " + "got:'{}'".format(sandbox_status)

    v.sandbox_on()
    sandbox_status = v.sandbox_status()
    assert sandbox_status == "on", "After enabling the sandbox mode the status should be 'on', " + "got:'{}'".format(sandbox_status)

    v.sandbox_off()
    sandbox_status = v.sandbox_status()
    assert sandbox_status == "off", "After disabling the sandbox mode the status should be 'off', " + "got:'{}'".format(sandbox_status)

    v.sandbox_on()
    v.halt()
    sandbox_status = v.sandbox_status()
    assert sandbox_status == "on", "After halting the VM the status should be 'on', " + "got:'{}'".format(sandbox_status)

    v.up()
    sandbox_status = v.sandbox_status()
    assert sandbox_status == "on", "After bringing the VM up again the status should be 'on', " + "got:'{}'".format(sandbox_status)

    test_file_contents = _read_test_file(v)
    print(test_file_contents)
    eq_(test_file_contents, None, "There should be no test file")

    _write_test_file(v, "foo")
    test_file_contents = _read_test_file(v)
    print(test_file_contents)
    eq_(test_file_contents, "foo", "The test file should read 'foo'")

    v.sandbox_rollback()
    time.sleep(10)  # https://github.com/jedi4ever/sahara/issues/16

    test_file_contents = _read_test_file(v)
    print(test_file_contents)
    eq_(test_file_contents, None, "There should be no test file")

    _write_test_file(v, "foo")
    test_file_contents = _read_test_file(v)
    print(test_file_contents)
    eq_(test_file_contents, "foo", "The test file should read 'foo'")
    v.sandbox_commit()
    _write_test_file(v, "bar")
    test_file_contents = _read_test_file(v)
    print(test_file_contents)
    eq_(test_file_contents, "bar", "The test file should read 'bar'")

    v.sandbox_rollback()
    time.sleep(10)  # https://github.com/jedi4ever/sahara/issues/16

    test_file_contents = _read_test_file(v)
    print(test_file_contents)
    eq_(test_file_contents, "foo", "The test file should read 'foo'")

    sandbox_status = v._parse_vagrant_sandbox_status("Usage: ...")
    eq_(sandbox_status, "not installed", "When 'vagrant sandbox status'" +
        " outputs vagrant help status should be 'not installed', " +
        "got:'{}'".format(sandbox_status))

    v.destroy()
    sandbox_status = v.sandbox_status()
    assert sandbox_status == "unknown", "After destroying the VM the status should be 'unknown', " + "got:'{}'".format(sandbox_status)


@with_setup(make_setup_vm(), teardown_vm)
def test_boxes():
    '''
    Test methods for manipulating boxes - adding, listing, removing.
    '''
    v = vagrant.Vagrant(TD)
    box_name = "python-vagrant-dummy-box"
    provider = "virtualbox"

    # Start fresh with no dummy box
    if box_name in list_box_names():
        subprocess.check_call(['vagrant', 'box', 'remove', box_name])

    # Test that there is no dummy box listed
    ok_(box_name not in [b.name for b in v.box_list()], "There should be no dummy box before it's added.")

    # Add a box
    v.box_add(box_name, TEST_BOX_URL)

    # Test that there is a dummy box listed
    box_listing = v.box_list()
    ok_((box_name, provider) in [(b.name, b.provider) for b in box_listing],
        'The box {box} for provider {provider} should be in the list returned by box_list(). box_list()={box_listing}'.format(
            box=box_name, provider=provider, box_listing=box_listing))


    # Remove dummy box using a box name and provider
    v.box_remove(box_name, provider)

    # Test that there is no dummy box listed
    ok_(box_name not in [b.name for b in v.box_list()], "There should be no dummy box after it has been removed.")

@with_setup(make_setup_vm(SHELL_PROVISION_VAGRANTFILE), teardown_vm)
def test_provisioning():
    '''
    Test provisioning support.  The tested provision config creates a file on
    the vm with the contents 'foo'.
    '''
    v = vagrant.Vagrant(TD)

    v.up(no_provision=True)
    test_file_contents = _read_test_file(v)
    eq_(test_file_contents, None, "There should be no test file after up()")

    v.provision()
    test_file_contents = _read_test_file(v)
    print("Contents: {}".format(test_file_contents))
    eq_(test_file_contents, "foo", "The test file should contain 'foo'")


@with_setup(make_setup_vm(MULTIVM_VAGRANTFILE), teardown_vm)
def test_multivm_lifecycle():
    v = vagrant.Vagrant(TD)

    # test getting multiple statuses at once
    eq_(v.status(VM_1)[0].state, v.NOT_CREATED)
    eq_(v.status(VM_2)[0].state, v.NOT_CREATED)

    v.up(vm_name=VM_1)
    eq_(v.status(VM_1)[0].state, v.RUNNING)
    eq_(v.status(VM_2)[0].state, v.NOT_CREATED)

    # start both vms
    v.up()
    eq_(v.status(VM_1)[0].state, v.RUNNING)
    eq_(v.status(VM_2)[0].state, v.RUNNING)

    v.halt(vm_name=VM_1)
    eq_(v.status(VM_1)[0].state, v.POWEROFF)
    eq_(v.status(VM_2)[0].state, v.RUNNING)

    v.destroy(vm_name=VM_1)
    eq_(v.status(VM_1)[0].state, v.NOT_CREATED)
    eq_(v.status(VM_2)[0].state, v.RUNNING)

    v.suspend(vm_name=VM_2)
    eq_(v.status(VM_1)[0].state, v.NOT_CREATED)
    eq_(v.status(VM_2)[0].state, v.SAVED)

    v.destroy(vm_name=VM_2)
    eq_(v.status(VM_1)[0].state, v.NOT_CREATED)
    eq_(v.status(VM_2)[0].state, v.NOT_CREATED)


@with_setup(make_setup_vm(MULTIVM_VAGRANTFILE), teardown_vm)
def test_multivm_config():
    '''
    Test methods retrieving configuration settings.
    '''
    v = vagrant.Vagrant(TD, quiet_stdout=False, quiet_stderr=False)
    v.up(vm_name=VM_1)
    command = "vagrant ssh-config " + VM_1
    ssh_config = compat.decode(subprocess.check_output(command, cwd=TD, shell=True))
    parsed_config = dict(line.strip().split(None, 1) for line in
                            ssh_config.splitlines() if line.strip() and not
                            line.strip().startswith('#'))

    user = v.user(vm_name=VM_1)
    expected_user = parsed_config["User"]
    eq_(user, expected_user)

    hostname = v.hostname(vm_name=VM_1)
    expected_hostname = parsed_config["HostName"]
    eq_(hostname, expected_hostname)

    port = v.port(vm_name=VM_1)
    expected_port = parsed_config["Port"]
    eq_(port, expected_port)

    user_hostname = v.user_hostname(vm_name=VM_1)
    eq_(user_hostname, "{}@{}".format(expected_user, expected_hostname))

    user_hostname_port = v.user_hostname_port(vm_name=VM_1)
    eq_(user_hostname_port,
        "{}@{}:{}".format(expected_user, expected_hostname, expected_port))

    keyfile = v.keyfile(vm_name=VM_1)
    try:
        eq_(keyfile, parsed_config["IdentityFile"])
    except AssertionError:
        # Vagrant 1.8 adds quotes around the filepath for the private key.
        eq_(keyfile, parsed_config["IdentityFile"].lstrip('"').rstrip('"'))


def test_make_file_cm():
    filename = os.path.join(TD, 'test.log')
    if os.path.exists(filename):
        os.remove(filename)

    # Test writing to the filehandle yielded by cm
    cm = vagrant.make_file_cm(filename)
    with cm() as fh:
        fh.write('one\n')

    with open(filename) as read_fh:
        assert read_fh.read() == 'one\n'

    # Test appending to the file yielded by cm
    with cm() as fh:
        fh.write('two\n')

    with open(filename) as read_fh:
        assert read_fh.read() == 'one\ntwo\n'


def _execute_command_in_vm(v, command):
    '''
    Run command via ssh on the test vagrant box.  Returns a tuple of the
    return code and output of the command.
    '''
    vagrant_exe = vagrant.get_vagrant_executable()

    if not vagrant_exe:
        raise RuntimeError(vagrant.VAGRANT_NOT_FOUND_WARNING)

    # ignore the fact that this host is not in our known hosts
    ssh_command = [vagrant_exe, 'ssh', '-c', command]
    return compat.decode(subprocess.check_output(ssh_command, cwd=v.root))


def _write_test_file(v, file_contents):
    '''
    Writes given contents to the test file.
    '''
    command = "echo '{}' > {}".format(file_contents, TEST_FILE_PATH)
    _execute_command_in_vm(v, command)


def _read_test_file(v):
    '''
    Returns the contents of the test file stored in the VM or None if there
    is no file.
    '''
    command = 'cat {}'.format(TEST_FILE_PATH)
    try:
        output = _execute_command_in_vm(v, command)
        return output.strip()
    except subprocess.CalledProcessError:
        return None


def _plugin_installed(v, plugin_name):
    plugins = v.plugin_list()
    return plugin_name in [plugin.name for plugin in plugins]
