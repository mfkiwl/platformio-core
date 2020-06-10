# Copyright (c) 2014-present PlatformIO <contact@platformio.org>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
import os
import random

import pytest
import requests

from platformio.commands.account import cli as cmd_account
from platformio.commands.org import cli as cmd_org
from platformio.commands.package import cli as cmd_package
from platformio.commands.team import cli as cmd_team
from platformio.downloader import FileDownloader
from platformio.unpacker import FileUnpacker

pytestmark = pytest.mark.skip()


@pytest.mark.skipif(
    not os.environ.get("TEST_EMAIL_LOGIN"),
    reason="requires TEST_EMAIL_LOGIN, TEST_EMAIL_PASSWORD environ variables",
)  # pylint:disable=too-many-arguments
def test_account(
    clirunner, validate_cliresult, receive_email, isolated_pio_home, tmpdir_factory
):
    username = "test-piocore-%s" % str(random.randint(0, 100000))
    splited_email = os.environ.get("TEST_EMAIL_LOGIN").split("@")
    email = "%s+%s@%s" % (splited_email[0], username, splited_email[1])
    firstname = "Test"
    lastname = "User"
    password = "Qwerty123!"

    # pio account register
    result = clirunner.invoke(
        cmd_account,
        [
            "register",
            "-u",
            username,
            "-e",
            email,
            "-p",
            password,
            "--firstname",
            firstname,
            "--lastname",
            lastname,
        ],
    )
    validate_cliresult(result)

    # email verification
    result = receive_email(email)
    link = (
        result.split("Click on the link below to start this process.")[1]
        .split("This link will expire within 12 hours.")[0]
        .strip()
    )
    session = requests.Session()
    result = session.get(link).text
    link = result.split('<a href="')[1].split('"', 1)[0]
    link = link.replace("&amp;", "&")
    session.get(link)

    # pio account login
    result = clirunner.invoke(cmd_account, ["login", "-u", username, "-p", password],)
    validate_cliresult(result)
    try:
        # pio account summary
        result = clirunner.invoke(cmd_account, ["show", "--json-output", "--offline"])
        validate_cliresult(result)
        json_result = json.loads(result.output.strip())
        assert not json_result.get("user_id")
        assert json_result.get("profile")
        assert json_result.get("profile").get("username")
        assert json_result.get("profile").get("email")
        assert not json_result.get("packages")
        assert not json_result.get("subscriptions")

        result = clirunner.invoke(cmd_account, ["show"])
        validate_cliresult(result)
        assert username in result.output
        # assert "100 Concurrent Remote Agents" in result.output

        result = clirunner.invoke(cmd_account, ["show", "--json-output"])
        validate_cliresult(result)
        json_result = json.loads(result.output.strip())
        assert json_result.get("user_id")
        assert json_result.get("profile")
        assert json_result.get("profile").get("username")
        assert json_result.get("profile").get("email")
        assert username == json_result.get("profile").get(
            "username"
        ) or username == json_result.get("profile").get("email")
        assert json_result.get("profile").get("firstname")
        assert json_result.get("profile").get("lastname")
        assert json_result.get("packages")
        assert json_result.get("packages")[0].get("name")
        assert json_result.get("packages")[0].get("path")
        assert json_result.get("subscriptions") is not None

        result = clirunner.invoke(cmd_account, ["show", "--json-output", "--offline"])
        validate_cliresult(result)
        json_result = json.loads(result.output.strip())
        assert json_result.get("user_id")
        assert json_result.get("profile")
        assert json_result.get("profile").get("username")
        assert json_result.get("profile").get("email")
        assert username == json_result.get("profile").get(
            "username"
        ) or username == json_result.get("profile").get("email")
        assert json_result.get("profile").get("firstname")
        assert json_result.get("profile").get("lastname")
        assert json_result.get("packages")
        assert json_result.get("packages")[0].get("name")
        assert json_result.get("packages")[0].get("path")
        assert json_result.get("subscriptions") is not None

        # pio account token
        result = clirunner.invoke(cmd_account, ["token", "--password", password,],)
        validate_cliresult(result)
        assert "Personal Authentication Token:" in result.output
        token = result.output.strip().split(": ")[-1]

        result = clirunner.invoke(
            cmd_account, ["token", "--password", password, "--json-output"],
        )
        validate_cliresult(result)
        json_result = json.loads(result.output.strip())
        assert json_result
        assert json_result.get("status") == "success"
        assert json_result.get("result") == token
        token = json_result.get("result")

        clirunner.invoke(cmd_account, ["logout"])

        result = clirunner.invoke(cmd_account, ["token", "--password", password,],)
        assert result.exit_code > 0
        assert result.exception
        assert "You are not authorized! Please log in to PIO Account" in str(
            result.exception
        )

        os.environ["PLATFORMIO_AUTH_TOKEN"] = token

        result = clirunner.invoke(
            cmd_account, ["token", "--password", password, "--json-output"],
        )
        validate_cliresult(result)
        json_result = json.loads(result.output.strip())
        assert json_result
        assert json_result.get("status") == "success"
        assert json_result.get("result") == token

        os.environ.pop("PLATFORMIO_AUTH_TOKEN")

        result = clirunner.invoke(
            cmd_account, ["login", "-u", username, "-p", password],
        )
        validate_cliresult(result)

        # pio account password
        new_password = "Testpassword123"
        result = clirunner.invoke(
            cmd_account,
            ["password", "--old-password", password, "--new-password", new_password,],
        )
        validate_cliresult(result)
        assert "Password successfully changed!" in result.output

        clirunner.invoke(cmd_account, ["logout"])

        result = clirunner.invoke(
            cmd_account, ["login", "-u", username, "-p", new_password],
        )
        validate_cliresult(result)

        result = clirunner.invoke(
            cmd_account,
            ["password", "--old-password", new_password, "--new-password", password,],
        )
        validate_cliresult(result)

        # pio account update
        firstname = "First " + str(random.randint(0, 100000))
        lastname = "Last" + str(random.randint(0, 100000))

        new_username = "username" + str(random.randint(0, 100000))
        new_email = "%s+new-%s@%s" % (splited_email[0], username, splited_email[1])
        result = clirunner.invoke(
            cmd_account,
            [
                "update",
                "--current-password",
                password,
                "--firstname",
                firstname,
                "--lastname",
                lastname,
                "--username",
                new_username,
                "--email",
                new_email,
            ],
        )
        validate_cliresult(result)
        assert "Profile successfully updated!" in result.output
        assert (
            "Please check your mail to verify your new email address and re-login. "
            in result.output
        )

        result = receive_email(new_email)
        link = (
            result.split("Click on the link below to start this process.")[1]
            .split("This link will expire within 12 hours.")[0]
            .strip()
        )
        session = requests.Session()
        result = session.get(link).text
        link = result.split('<a href="')[1].split('"', 1)[0]
        link = link.replace("&amp;", "&")
        session.get(link)

        result = clirunner.invoke(cmd_account, ["show"],)
        assert result.exit_code > 0
        assert result.exception
        assert "You are not authorized! Please log in to PIO Account" in str(
            result.exception
        )

        result = clirunner.invoke(
            cmd_account, ["login", "-u", new_username, "-p", password],
        )
        validate_cliresult(result)

        # pio account destroy with linked resource

        package_url = "https://github.com/bblanchon/ArduinoJson/archive/v6.11.0.tar.gz"

        tmp_dir = tmpdir_factory.mktemp("package")
        fd = FileDownloader(package_url, str(tmp_dir))
        pkg_dir = tmp_dir.mkdir("raw_package")
        fd.start(with_progress=False, silent=True)
        with FileUnpacker(fd.get_filepath()) as unpacker:
            unpacker.unpack(str(pkg_dir), with_progress=False, silent=True)

        result = clirunner.invoke(cmd_package, ["publish", str(pkg_dir)],)
        validate_cliresult(result)
        try:
            result = receive_email(new_email)
            assert "Congrats" in result
            assert "was published" in result
        except:  # pylint:disable=bare-except
            pass

        result = clirunner.invoke(cmd_account, ["destroy"], "y")
        assert result.exit_code != 0
        assert (
            "We can not destroy the %s account due to 1 linked resources from registry"
            % username
        )

        result = clirunner.invoke(cmd_package, ["unpublish", "ArduinoJson"],)
        validate_cliresult(result)
    finally:
        clirunner.invoke(cmd_account, ["destroy"], "y")


@pytest.mark.skipif(
    not os.environ.get("TEST_EMAIL_LOGIN"),
    reason="requires TEST_EMAIL_LOGIN, TEST_EMAIL_PASSWORD environ variables",
)  # pylint:disable=too-many-arguments
def test_org(clirunner, validate_cliresult, receive_email, isolated_pio_home):
    username = "test-piocore-%s" % str(random.randint(0, 100000))
    splited_email = os.environ.get("TEST_EMAIL_LOGIN").split("@")
    email = "%s+%s@%s" % (splited_email[0], username, splited_email[1])
    firstname = "Test"
    lastname = "User"
    password = "Qwerty123!"

    # pio account register
    result = clirunner.invoke(
        cmd_account,
        [
            "register",
            "-u",
            username,
            "-e",
            email,
            "-p",
            password,
            "--firstname",
            firstname,
            "--lastname",
            lastname,
        ],
    )
    validate_cliresult(result)

    # email verification
    result = receive_email(email)
    link = (
        result.split("Click on the link below to start this process.")[1]
        .split("This link will expire within 12 hours.")[0]
        .strip()
    )
    session = requests.Session()
    result = session.get(link).text
    link = result.split('<a href="')[1].split('"', 1)[0]
    link = link.replace("&amp;", "&")
    session.get(link)

    # pio account login
    result = clirunner.invoke(cmd_account, ["login", "-u", username, "-p", password],)
    validate_cliresult(result)

    orgname = "testorg-piocore-%s" % str(random.randint(0, 100000))
    display_name = "Test Org for PIO Core"
    second_username = "ivankravets"
    try:
        # pio org create
        result = clirunner.invoke(
            cmd_org,
            ["create", "--email", email, "--displayname", display_name, orgname],
        )
        validate_cliresult(result)

        # pio org list
        result = clirunner.invoke(cmd_org, ["list", "--json-output"])
        validate_cliresult(result)
        json_result = json.loads(result.output.strip())
        assert json_result == [
            {
                "orgname": orgname,
                "displayname": display_name,
                "email": email,
                "owners": [
                    {"username": username, "firstname": firstname, "lastname": lastname}
                ],
            }
        ]

        # pio org add (owner)
        result = clirunner.invoke(cmd_org, ["add", orgname, second_username])
        validate_cliresult(result)

        result = clirunner.invoke(cmd_org, ["list", "--json-output"])
        validate_cliresult(result)
        assert second_username in result.output

        # pio org remove (owner)
        result = clirunner.invoke(cmd_org, ["remove", orgname, second_username])
        validate_cliresult(result)

        result = clirunner.invoke(cmd_org, ["list", "--json-output"])
        validate_cliresult(result)
        assert second_username not in result.output

        # pio org update
        new_orgname = "neworg-piocore-%s" % str(random.randint(0, 100000))
        new_display_name = "Test Org for PIO Core"

        result = clirunner.invoke(
            cmd_org,
            [
                "update",
                orgname,
                "--new-orgname",
                new_orgname,
                "--displayname",
                new_display_name,
            ],
        )
        validate_cliresult(result)

        result = clirunner.invoke(cmd_org, ["list", "--json-output"])
        validate_cliresult(result)
        json_result = json.loads(result.output.strip())
        assert json_result == [
            {
                "orgname": new_orgname,
                "displayname": new_display_name,
                "email": email,
                "owners": [
                    {"username": username, "firstname": firstname, "lastname": lastname}
                ],
            }
        ]

        result = clirunner.invoke(
            cmd_org,
            [
                "update",
                new_orgname,
                "--new-orgname",
                orgname,
                "--displayname",
                display_name,
            ],
        )
        validate_cliresult(result)
    finally:
        clirunner.invoke(cmd_org, ["destroy", orgname], "y")
        clirunner.invoke(cmd_account, ["destroy"], "y")


@pytest.mark.skipif(
    not os.environ.get("TEST_EMAIL_LOGIN"),
    reason="requires TEST_EMAIL_LOGIN, TEST_EMAIL_PASSWORD environ variables",
)  # pylint:disable=too-many-arguments
def test_team(clirunner, validate_cliresult, receive_email, isolated_pio_home):
    username = "test-piocore-%s" % str(random.randint(0, 100000))
    splited_email = os.environ.get("TEST_EMAIL_LOGIN").split("@")
    email = "%s+%s@%s" % (splited_email[0], username, splited_email[1])
    firstname = "Test"
    lastname = "User"
    password = "Qwerty123!"

    # pio account register
    result = clirunner.invoke(
        cmd_account,
        [
            "register",
            "-u",
            username,
            "-e",
            email,
            "-p",
            password,
            "--firstname",
            firstname,
            "--lastname",
            lastname,
        ],
    )
    validate_cliresult(result)

    # email verification
    result = receive_email(email)
    link = (
        result.split("Click on the link below to start this process.")[1]
        .split("This link will expire within 12 hours.")[0]
        .strip()
    )
    session = requests.Session()
    result = session.get(link).text
    link = result.split('<a href="')[1].split('"', 1)[0]
    link = link.replace("&amp;", "&")
    session.get(link)

    # pio account login
    result = clirunner.invoke(cmd_account, ["login", "-u", username, "-p", password],)
    validate_cliresult(result)

    orgname = "testorg-piocore-%s" % str(random.randint(0, 100000))
    display_name = "Test Org for PIO Core"

    # pio org create
    result = clirunner.invoke(
        cmd_org, ["create", "--email", email, "--displayname", display_name, orgname]
    )
    validate_cliresult(result)

    teamname = "test-" + str(random.randint(0, 100000))
    team_description = "team for CI test"
    second_username = "ivankravets"
    try:
        # pio team create
        result = clirunner.invoke(
            cmd_team,
            [
                "create",
                "%s:%s" % (orgname, teamname),
                "--description",
                team_description,
            ],
        )
        validate_cliresult(result)

        # pio team list
        result = clirunner.invoke(cmd_team, ["list", "%s" % orgname, "--json-output"],)
        validate_cliresult(result)
        json_result = json.loads(result.output.strip())
        for item in json_result:
            del item["id"]
        assert json_result == [
            {"name": teamname, "description": team_description, "members": []}
        ]

        # pio team add (member)
        result = clirunner.invoke(
            cmd_team, ["add", "%s:%s" % (orgname, teamname), second_username],
        )
        validate_cliresult(result)

        result = clirunner.invoke(cmd_team, ["list", "%s" % orgname, "--json-output"],)
        validate_cliresult(result)
        assert second_username in result.output

        # pio team remove (member)
        result = clirunner.invoke(
            cmd_team, ["remove", "%s:%s" % (orgname, teamname), second_username],
        )
        validate_cliresult(result)

        result = clirunner.invoke(cmd_team, ["list", "%s" % orgname, "--json-output"],)
        validate_cliresult(result)
        assert second_username not in result.output

        # pio team update
        new_teamname = "new-" + str(random.randint(0, 100000))
        newteam_description = "Updated Description"
        result = clirunner.invoke(
            cmd_team,
            [
                "update",
                "%s:%s" % (orgname, teamname),
                "--name",
                new_teamname,
                "--description",
                newteam_description,
            ],
        )
        validate_cliresult(result)

        result = clirunner.invoke(cmd_team, ["list", "%s" % orgname, "--json-output"],)
        validate_cliresult(result)
        json_result = json.loads(result.output.strip())
        for item in json_result:
            del item["id"]
        assert json_result == [
            {"name": new_teamname, "description": newteam_description, "members": []}
        ]

        result = clirunner.invoke(
            cmd_team,
            [
                "update",
                "%s:%s" % (orgname, new_teamname),
                "--name",
                teamname,
                "--description",
                team_description,
            ],
        )
        validate_cliresult(result)
    finally:
        clirunner.invoke(cmd_team, ["destroy", "%s:%s" % (orgname, teamname)], "y")
        clirunner.invoke(cmd_org, ["destroy", orgname], "y")
        clirunner.invoke(cmd_account, ["destroy"], "y")
