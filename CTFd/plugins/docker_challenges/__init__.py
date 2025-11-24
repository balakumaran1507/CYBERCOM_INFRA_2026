import traceback

from CTFd.plugins.challenges import BaseChallenge, CHALLENGE_CLASSES, get_chal_class
from CTFd.plugins.flags import get_flag_class
from CTFd.utils.user import get_ip
from CTFd.utils.uploads import delete_file
from CTFd.plugins import register_plugin_assets_directory, bypass_csrf_protection
from CTFd.schemas.tags import TagSchema
from CTFd.models import db, ma, Challenges, Teams, Users, Solves, Submissions, Flags, Files, Hints, Tags
from CTFd.utils.decorators import admins_only, authed_only, during_ctf_time_only, require_verified_emails
from CTFd.utils.decorators.visibility import check_challenge_visibility, check_score_visibility
from CTFd.utils.user import get_current_team
from CTFd.utils.user import get_current_user
from CTFd.utils.user import is_admin, authed
from CTFd.utils.config import is_teams_mode
from CTFd.api import CTFd_API_v1
from CTFd.api.v1.scoreboard import ScoreboardDetail
import CTFd.utils.scores
from CTFd.api.v1.challenges import ChallengeList, Challenge
from flask_restx import Namespace, Resource
from flask import request, Blueprint, jsonify, abort, render_template, url_for, redirect, session
# from flask_wtf import FlaskForm
from wtforms import (
    FileField,
    HiddenField,
    PasswordField,
    RadioField,
    SelectField,
    StringField,
    TextAreaField,
    SelectMultipleField,
    BooleanField,
)
# from wtforms import TextField, SubmitField, BooleanField, HiddenField, FileField, SelectMultipleField
from wtforms.validators import DataRequired, ValidationError, InputRequired
from werkzeug.utils import secure_filename
import requests
import tempfile
from CTFd.utils.dates import unix_time
from datetime import datetime, timedelta
import json
import hashlib
import random
from CTFd.plugins import register_admin_plugin_menu_bar

from CTFd.forms import BaseForm
from CTFd.forms.fields import SubmitField
from CTFd.utils.config import get_themes

from pathlib import Path
import secrets
import re

# CYBERCOM: Import flag encryption utilities
from .crypto_utils import encrypt_flag, decrypt_flag, constant_time_compare, redact_flag

# === CRE IMPORTS ===
from .models_cre import ContainerEvent, ContainerRuntimePolicy
from .cre import cre, RuntimePolicy
from .cleanup_worker import cleanup_worker


def generate_dynamic_flag(template):
    """
    Generate a dynamic flag based on the template with CYBERCOM branding.

    Template format: "injects_<hex>_hurts_yk_<hex>"
    Each <hex> placeholder is replaced with 6 characters of secure random hex.
    Final flag is wrapped in CYBERCOM{...}

    Args:
        template (str): Flag template with <hex> placeholders

    Returns:
        str: Generated flag in format CYBERCOM{template_with_hex_replaced}

    Example:
        >>> generate_dynamic_flag("injects_<hex>_hurts_yk_<hex>")
        'CYBERCOM{injects_4fa2c1_hurts_yk_b92ed0}'
    """
    if not template:
        template = "default_<hex>"
        print(f"[FLAG GEN] WARNING: Empty template provided, using default")

    print(f"[FLAG GEN] Input template: '{template}'")

    # Find all <hex> placeholders
    hex_pattern = r'<hex>'

    # Replace each <hex> with 6 characters of secure random hex
    def replace_hex(match):
        return secrets.token_hex(3)  # 3 bytes = 6 hex characters

    # Replace all <hex> placeholders
    flag_content = re.sub(hex_pattern, replace_hex, template)

    # Wrap in CYBERCOM{...}
    flag = f"CYBERCOM{{{flag_content}}}"

    print(f"[FLAG GEN] Generated flag: '{flag}'")
    return flag


class DockerConfig(db.Model):
    """
	Docker Config Model. This model stores the config for docker API connections.
	"""
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column("hostname", db.String(64), index=True)
    tls_enabled = db.Column("tls_enabled", db.Boolean, default=False, index=True)
    ca_cert = db.Column("ca_cert", db.String(2200), index=True)
    client_cert = db.Column("client_cert", db.String(2000), index=True)
    client_key = db.Column("client_key", db.String(3300), index=True)
    repositories = db.Column("repositories", db.String(1024), index=True)


class DockerChallengeTracker(db.Model):
    """
	Docker Container Tracker. This model stores the users/teams active docker containers.
	Enhanced with CRE (CYBERCOM Runtime Engine) lifecycle management.
	"""
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column("team_id", db.String(64), index=True)
    user_id = db.Column("user_id", db.String(64), index=True)
    docker_image = db.Column("docker_image", db.String(64), index=True)
    timestamp = db.Column("timestamp", db.Integer, index=True)
    revert_time = db.Column("revert_time", db.Integer, index=True)

    # === CRE LIFECYCLE FIELDS ===
    extension_count = db.Column('extension_count', db.Integer, default=0, index=True)
    created_at = db.Column('created_at', db.DateTime, default=datetime.utcnow)
    last_extended_at = db.Column('last_extended_at', db.DateTime, nullable=True)

    instance_id = db.Column("instance_id", db.String(128), index=True)
    ports = db.Column('ports', db.String(128), index=True)
    host = db.Column('host', db.String(128), index=True)
    challenge = db.Column('challenge', db.String(256), index=True)


class DynamicFlagMapping(db.Model):
    """
	CYBERCOM CTF - Dynamic Flag Mapping (Production v1.0)

	Simplified, high-performance, container-bound dynamic flag system.

	Core Principles:
	- ONE flag per container (UNIQUE container_id constraint)
	- Encrypted at rest (Fernet AES-128-CBC + HMAC-SHA256)
	- Constant-time comparison (prevents timing attacks)
	- Minimal state, maximum performance

	Security:
	- Flags encrypted before storage
	- Container isolation prevents cross-instance reuse
	- Constant-time validation prevents side-channel attacks

	Performance:
	- O(1) lookup via UNIQUE index on container_id
	- No state transitions = no extra writes
	- Single query validation path

	Future Compatibility:
	- Ready for CTFd Whale integration
	- Supports key rotation via encryption_key_id
	- Audit trail via created_at timestamp

	CASCADE DELETE: When challenge is deleted, all flags are automatically removed.
	"""
    __tablename__ = 'dynamic_flag_mapping'

    id = db.Column(db.Integer, primary_key=True)

    # User/Team identification (mutually exclusive)
    user_id = db.Column("user_id", db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True)
    team_id = db.Column("team_id", db.Integer, db.ForeignKey('teams.id', ondelete='CASCADE'), nullable=True, index=True)

    # Challenge reference
    challenge_id = db.Column("challenge_id", db.Integer, db.ForeignKey('challenges.id', ondelete='CASCADE'), nullable=False, index=True)

    # CRITICAL: One-to-one flag-container binding
    # UNIQUE constraint ensures no duplicate flags per container
    # This is the ONLY lookup key for validation (O(1) performance)
    container_id = db.Column("container_id", db.String(128), unique=True, nullable=False, index=True)

    # Encrypted flag storage (Fernet symmetric encryption)
    # Decrypted only during validation, never stored in plaintext
    encrypted_flag = db.Column("encrypted_flag", db.Text, nullable=False)

    # Audit trail (minimal, for future analytics)
    created_at = db.Column("created_at", db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Future: Key rotation support (currently always 1)
    encryption_key_id = db.Column("encryption_key_id", db.Integer, default=1, nullable=False)

class DockerConfigForm(BaseForm):
    id = HiddenField()
    hostname = StringField(
        "Docker Hostname", description="The Hostname/IP and Port of your Docker Server"
    )
    tls_enabled = RadioField('TLS Enabled?')
    ca_cert = FileField('CA Cert')
    client_cert = FileField('Client Cert')
    client_key = FileField('Client Key')
    repositories = SelectMultipleField('Repositories')
    submit = SubmitField('Submit')


def define_docker_admin(app):
    admin_docker_config = Blueprint('admin_docker_config', __name__, template_folder='templates',
                                    static_folder='assets')

    @admin_docker_config.route("/admin/docker_config", methods=["GET", "POST"])
    @admins_only
    def docker_config():
        docker = DockerConfig.query.filter_by(id=1).first()
        form = DockerConfigForm()
        if request.method == "POST":
            if docker:
                b = docker
            else:
                b = DockerConfig()
            try:
                ca_cert = request.files['ca_cert'].stream.read()
            except:
                traceback.print_exc()
                ca_cert = ''
            try:
                client_cert = request.files['client_cert'].stream.read()
            except:
                traceback.print_exc()
                client_cert = ''
            try:
                client_key = request.files['client_key'].stream.read()
            except:
                traceback.print_exc()
                client_key = ''
            if len(ca_cert) != 0: b.ca_cert = ca_cert
            if len(client_cert) != 0: b.client_cert = client_cert
            if len(client_key) != 0: b.client_key = client_key
            b.hostname = request.form['hostname']
            b.tls_enabled = request.form['tls_enabled']
            if b.tls_enabled == "True":
                b.tls_enabled = True
            else:
                b.tls_enabled = False
            if not b.tls_enabled:
                b.ca_cert = None
                b.client_cert = None
                b.client_key = None
            try:
                b.repositories = ','.join(request.form.to_dict(flat=False)['repositories'])
            except:
                traceback.print_exc()
                b.repositories = None
            db.session.add(b)
            db.session.commit()
            docker = DockerConfig.query.filter_by(id=1).first()
        try:
            repos = get_repositories(docker)
        except:
            traceback.print_exc()
            repos = list()
        if len(repos) == 0:
            form.repositories.choices = [("ERROR", "Failed to Connect to Docker")]
        else:
            form.repositories.choices = [(d, d) for d in repos]
        dconfig = DockerConfig.query.first()
        try:
            selected_repos = dconfig.repositories
            if selected_repos == None:
                selected_repos = list()
        # selected_repos = dconfig.repositories.split(',')
        except:
            traceback.print_exc()
            selected_repos = []
        return render_template("docker_config.html", config=dconfig, form=form, repos=selected_repos)

    app.register_blueprint(admin_docker_config)


def define_docker_status(app):
    admin_docker_status = Blueprint('admin_docker_status', __name__, template_folder='templates',
                                    static_folder='assets')

    @admin_docker_status.route("/admin/docker_status", methods=["GET", "POST"])
    @admins_only
    def docker_admin():
        docker_config = DockerConfig.query.filter_by(id=1).first()
        docker_tracker = DockerChallengeTracker.query.all()
        for i in docker_tracker:
            if is_teams_mode():
                name = Teams.query.filter_by(id=i.team_id).first()
                i.team_id = name.name
            else:
                name = Users.query.filter_by(id=i.user_id).first()
                i.user_id = name.name
        return render_template("admin_docker_status.html", dockers=docker_tracker)

    app.register_blueprint(admin_docker_status)


kill_container = Namespace("nuke", description='Endpoint to nuke containers')


@kill_container.route("", methods=['POST', 'GET'])
class KillContainerAPI(Resource):
    @admins_only
    def get(self):
        container = request.args.get('container')
        full = request.args.get('all')
        docker_config = DockerConfig.query.filter_by(id=1).first()
        docker_tracker = DockerChallengeTracker.query.all()
        if full == "true":
            for c in docker_tracker:
                delete_container(docker_config, c.instance_id)
                DockerChallengeTracker.query.filter_by(instance_id=c.instance_id).delete()
                db.session.commit()

        elif container != 'null' and container in [c.instance_id for c in docker_tracker]:
            delete_container(docker_config, container)
            DockerChallengeTracker.query.filter_by(instance_id=container).delete()
            db.session.commit()

        else:
            return False
        return True


# ============================================================
# CRE (CYBERCOM Runtime Engine) - Extension API
# ============================================================
container_extension_namespace = Namespace(
    "container_extension",
    description='CRE container lifecycle management endpoints'
)


@container_extension_namespace.route("/extend", methods=['POST'])
class ContainerExtension(Resource):
    """
    Extend container lifetime.

    Request JSON:
        {
            "challenge_id": 5
        }

    Response JSON:
        {
            "success": true,
            "message": "Container extended by 15 minutes (extension 1/5)"
        }

    Errors:
        - 400: Missing challenge_id
        - 404: No active container
        - 403: Max extensions reached
        - 500: Internal error
    """
    @authed_only
    def post(self):
        from CTFd.utils.user import get_current_user
        from CTFd.utils.config import is_teams_mode

        # Parse request
        data = request.get_json()
        if not data or 'challenge_id' not in data:
            return {
                'success': False,
                'message': 'challenge_id required'
            }, 400

        challenge_id = data['challenge_id']

        # Validate challenge_id is integer
        try:
            challenge_id = int(challenge_id)
        except (ValueError, TypeError):
            return {
                'success': False,
                'message': 'Invalid challenge_id'
            }, 400

        # Get current user/team
        user = get_current_user()
        team_id = user.team_id if is_teams_mode() else None

        # Call CRE
        success, message = cre.extend_instance(
            user_id=user.id,
            challenge_id=challenge_id,
            team_id=team_id
        )

        status_code = 200 if success else 400
        return {
            'success': success,
            'message': message
        }, status_code


@container_extension_namespace.route("/status", methods=['GET'])
class ContainerStatus(Resource):
    """
    Get container status (for UI updates).

    Query params:
        challenge_id: int

    Response:
        {
            "active": true,
            "container_id": "abc123...",
            "remaining_seconds": 450,
            "extension_count": 2,
            "max_extensions": 5
        }
    """
    @authed_only
    def get(self):
        from CTFd.utils.user import get_current_user
        from CTFd.utils.config import is_teams_mode

        challenge_id = request.args.get('challenge_id', type=int)
        if not challenge_id:
            return {'success': False, 'message': 'challenge_id required'}, 400

        user = get_current_user()
        team_id = user.team_id if is_teams_mode() else None

        status = cre.get_instance_status(
            user_id=user.id,
            challenge_id=challenge_id,
            team_id=team_id
        )

        if not status:
            return {'active': False}, 200

        return status, 200


def do_request(docker, url, headers=None, method='GET'):
    tls = docker.tls_enabled
    prefix = 'https' if tls else 'http'
    host = docker.hostname
    URL_TEMPLATE = '%s://%s' % (prefix, host)
    try:
        if tls:
            cert, verify = get_client_cert(docker)
            if (method == 'GET'):
                r = requests.get(url=f"%s{url}" % URL_TEMPLATE, cert=cert, verify=verify, headers=headers)
            elif (method == 'DELETE'):
                r = requests.delete(url=f"%s{url}" % URL_TEMPLATE, cert=cert, verify=verify, headers=headers)
            # Clean up the cert files:
            for file_path in [*cert, verify]:
                if file_path:
                    Path(file_path).unlink(missing_ok=True)
        else:
            if (method == 'GET'):
                r = requests.get(url=f"%s{url}" % URL_TEMPLATE, headers=headers)
            elif (method == 'DELETE'):
                r = requests.delete(url=f"%s{url}" % URL_TEMPLATE, headers=headers)
    except:
        traceback.print_exc()
        r = []
    return r


def get_client_cert(docker):
    # this can be done more efficiently, but works for now.
    try:
        ca = docker.ca_cert
        client = docker.client_cert
        ckey = docker.client_key
        ca_file = tempfile.NamedTemporaryFile(delete=False)
        ca_file.write(ca.encode())
        ca_file.seek(0)
        client_file = tempfile.NamedTemporaryFile(delete=False)
        client_file.write(client.encode())
        client_file.seek(0)
        key_file = tempfile.NamedTemporaryFile(delete=False)
        key_file.write(ckey.encode())
        key_file.seek(0)
        CERT = (client_file.name, key_file.name)
    except:
        traceback.print_exc()
        CERT = None
    return CERT, ca_file.name


# For the Docker Config Page. Gets the Current Repositories available on the Docker Server.
def get_repositories(docker, tags=False, repos=False):
    """
    Get available Docker repositories from Docker server.

    Safely handles images with missing or None RepoTags (dangling images, registry inconsistencies).
    """
    try:
        r = do_request(docker, '/images/json?all=1')
        result = list()

        for i in r.json():
            # Safe access to RepoTags with .get() - handles missing key and None values
            repo_tags = i.get('RepoTags', [])

            # Skip images with no tags or None tags (dangling images)
            if not repo_tags:
                continue

            # Safe access to first tag (already validated above)
            first_tag = repo_tags[0]

            # Skip <none> tagged images
            if first_tag.split(':')[0] == '<none>':
                continue

            # Filter by repos if specified
            if repos:
                if first_tag.split(':')[0] not in repos:
                    continue

            # Append result based on tags flag
            if not tags:
                result.append(first_tag.split(':')[0])
            else:
                result.append(first_tag)

        return list(set(result))

    except Exception as e:
        print(f"[CYBERCOM ERROR] Failed to get repositories: {e}")
        return []  # Safe fallback - return empty list


def get_unavailable_ports(docker):
    """
    Returns a list of ports that are already publicly exposed by running containers.
    This version is SAFE for Whale + FRP + Docker edge cases.
    """
    result = []

    try:
        r = do_request(docker, '/containers/json?all=1')
        containers = r.json()
    except Exception as e:
        print(f"[CYBERCOM ERROR] Failed to list containers: {e}")
        return result

    for container in containers:
        try:
            ports = container.get('Ports', [])
        except Exception:
            continue

        if not ports:
            continue

        for p in ports:
            # Some containers do NOT have PublicPort (common with Whale/FRP)
            public_port = p.get("PublicPort")

            # Only collect real exposed ports
            if public_port is not None:
                result.append(public_port)

    return result


def get_required_ports(docker, image):
    """
    Get required ports from Docker image.

    Returns empty list if image has no exposed ports (e.g., alpine, scratch).
    Logs warning for port-less images to aid debugging.
    """
    try:
        r = do_request(docker, f'/images/{image}/json?all=1')
        image_info = r.json()

        # Safe nested access with .get() chain
        config = image_info.get('Config', {})
        exposed_ports = config.get('ExposedPorts', {})

        if not exposed_ports:
            print(f"[CYBERCOM WARNING] Image {image} has no exposed ports - creating port-less container")
            return []

        return list(exposed_ports.keys())

    except Exception as e:
        print(f"[CYBERCOM ERROR] Failed to get required ports for {image}: {e}")
        return []  # Safe fallback - no ports required


def create_container(docker, image, team, portbl, flag=None):
    """
    Create a Docker container with optional flag injection.

    Args:
        docker: DockerConfig object
        image: Docker image name
        team: Team/user name
        portbl: List of blocked ports
        flag: Optional flag to inject into container (as ENV and /flag.txt)

    Returns:
        tuple: (result dict, request data)
    """
    tls = docker.tls_enabled
    CERT = None
    if not tls:
        prefix = 'http'
    else:
        prefix = 'https'
    host = docker.hostname
    URL_TEMPLATE = '%s://%s' % (prefix, host)
    needed_ports = get_required_ports(docker, image)
    team = hashlib.md5(team.encode("utf-8")).hexdigest()[:10]

    # Safe tag extraction - handle images without explicit tags (e.g., "nginx" vs "nginx:latest")
    image_tag = image.split(':')[1] if ':' in image else 'latest'
    container_name = f"{image_tag}_{team}"
    assigned_ports = dict()
    for i in needed_ports:
        while True:
            assigned_port = random.choice(range(30000, 60000))
            if assigned_port not in portbl:
                assigned_ports['%s/tcp' % assigned_port] = {}
                break
    ports = dict()
    bindings = dict()
    tmp_ports = list(assigned_ports.keys())
    for i in needed_ports:
        ports[i] = {}
        bindings[i] = [{"HostPort": tmp_ports.pop()}]

    # Prepare container configuration
    container_config = {
        "Image": image,
        "ExposedPorts": ports,
        "HostConfig": {"PortBindings": bindings}
    }

    # Inject flag as environment variable and via command to write to /flag.txt
    if flag:
        container_config["Env"] = [f"FLAG={flag}"]
        # Write flag to /flag.txt and start nginx (nginx-compatible)
        # NOTE: This is optimized for nginx. For other services, adjust the final command.
        container_config["Cmd"] = [
            "sh",
            "-c",
            "echo \"$FLAG\" > /flag.txt && nginx -g 'daemon off;'"
        ]

    headers = {'Content-Type': "application/json"}
    data = json.dumps(container_config)

    if tls:
        cert, verify = get_client_cert(docker)
        r = requests.post(url="%s/containers/create?name=%s" % (URL_TEMPLATE, container_name), cert=cert,
                      verify=verify, data=data, headers=headers)
        result = r.json()

        # Validate Docker response before accessing 'Id'
        if 'Id' not in result:
            error_msg = result.get('message', 'Unknown Docker error')
            print(f"[CYBERCOM ERROR] Container creation failed: {error_msg}")
            print(f"[CYBERCOM DEBUG] Docker response: {result}")
            raise Exception(f"Docker container creation failed: {error_msg}")

        s = requests.post(url="%s/containers/%s/start" % (URL_TEMPLATE, result['Id']), cert=cert, verify=verify,
                          headers=headers)
        # Clean up the cert files:
        for file_path in [*cert, verify]:
            if file_path:
                Path(file_path).unlink(missing_ok=True)

    else:
        r = requests.post(url="%s/containers/create?name=%s" % (URL_TEMPLATE, container_name),
                          data=data, headers=headers)
        print(r.request.method, r.request.url, r.request.body)
        result = r.json()
        print(result)

        # Validate Docker response before accessing 'Id'
        if 'Id' not in result:
            error_msg = result.get('message', 'Unknown Docker error')
            print(f"[CYBERCOM ERROR] Container creation failed: {error_msg}")
            print(f"[CYBERCOM DEBUG] Docker response: {result}")
            raise Exception(f"Docker container creation failed: {error_msg}")

        # name conflicts are not handled properly
        s = requests.post(url="%s/containers/%s/start" % (URL_TEMPLATE, result['Id']), headers=headers)
    return result, data


def delete_container(docker, instance_id):
    headers = {'Content-Type': "application/json"}
    do_request(docker, f'/containers/{instance_id}?force=true', headers=headers, method='DELETE')
    return True


class DockerChallengeType(BaseChallenge):
    id = "docker"
    name = "docker"
    templates = {
        'create': '/plugins/docker_challenges/assets/create.html',
        'update': '/plugins/docker_challenges/assets/update.html',
        'view': '/plugins/docker_challenges/assets/view.html',
    }
    scripts = {
        'create': '/plugins/docker_challenges/assets/create.js',
        'update': '/plugins/docker_challenges/assets/update.js',
        'view': '/plugins/docker_challenges/assets/view.js',
    }
    route = '/plugins/docker_challenges/assets'
    blueprint = Blueprint('docker_challenges', __name__, template_folder='templates', static_folder='assets')

    @staticmethod
    def update(challenge, request):
        """
		This method is used to update the information associated with a challenge. This should be kept strictly to the
		Challenges table and any child tables.

		:param challenge:
		:param request:
		:return:
		"""
        data = request.form or request.get_json()
        for attr, value in data.items():
            setattr(challenge, attr, value)

        db.session.commit()
        return challenge

    @staticmethod
    def delete(challenge):
        """
		This method is used to delete the resources used by a challenge.
		NOTE: Will need to kill all containers here

		CRITICAL: Manually delete DynamicFlagMapping entries before challenge deletion
		to prevent foreign key constraint errors. CASCADE delete is set on the model,
		but explicit cleanup is safer for production.

		:param challenge:
		:return:
		"""
        # Clean up dynamic flag mappings (production-safe explicit cleanup)
        flag_count = DynamicFlagMapping.query.filter_by(challenge_id=challenge.id).delete()
        if flag_count > 0:
            print(f"[CHALLENGE DELETE] Removed {flag_count} dynamic flag mapping(s) for challenge {challenge.id}")

        Submissions.query.filter_by(challenge_id=challenge.id).delete()
        Solves.query.filter_by(challenge_id=challenge.id).delete()
        Flags.query.filter_by(challenge_id=challenge.id).delete()
        files = Files.query.filter_by(challenge_id=challenge.id).all()
        for f in files:
            delete_file(f.id)
        Files.query.filter_by(challenge_id=challenge.id).delete()
        Tags.query.filter_by(challenge_id=challenge.id).delete()
        Hints.query.filter_by(challenge_id=challenge.id).delete()
        DockerChallenge.query.filter_by(id=challenge.id).delete()
        Challenges.query.filter_by(id=challenge.id).delete()
        db.session.commit()

    @staticmethod
    def read(challenge):
        """
		This method is in used to access the data of a challenge in a format processable by the front end.

		:param challenge:
		:return: Challenge object, data dictionary to be returned to the user
		"""
        challenge = DockerChallenge.query.filter_by(id=challenge.id).first()
        data = {
            'id': challenge.id,
            'name': challenge.name,
            'value': challenge.value,
            'docker_image': challenge.docker_image,
            'flag_template': challenge.flag_template,
            'description': challenge.description,
            'category': challenge.category,
            'state': challenge.state,
            'max_attempts': challenge.max_attempts,
            'type': challenge.type,
            'type_data': {
                'id': DockerChallengeType.id,
                'name': DockerChallengeType.name,
                'templates': DockerChallengeType.templates,
                'scripts': DockerChallengeType.scripts,
            }
        }
        return data

    @staticmethod
    def create(request):
        """
		This method is used to process the challenge creation request.

		:param request:
		:return:
		"""
        data = request.form or request.get_json()
        challenge = DockerChallenge(**data)
        db.session.add(challenge)
        db.session.commit()
        return challenge

    @staticmethod
    def attempt(challenge, request):
        """
		This method is used to check whether a given input is right or wrong. It does not make any changes and should
		return a boolean for correctness and a string to be shown to the user. It is also in charge of parsing the
		user's input from the request itself.

		For Docker challenges with dynamic flags, this validates against the user's active container flag.

		:param challenge: The Challenge object from the database
		:param request: The request the user submitted
		:return: (boolean, string)
		"""

        # === CYBERCOM: SIMPLIFIED FLAG VALIDATION ===

        data = request.form or request.get_json()
        submission = data["submission"].strip()

        # STEP 1: Identify user/team and get their active container
        if is_teams_mode():
            session = get_current_team()
            print(f"[CYBERCOM] Validating for team {session.id}, challenge {challenge.id}")

            # Find active container for this team + challenge
            tracker = DockerChallengeTracker.query.filter_by(
                team_id=session.id,
                docker_image=challenge.docker_image
            ).first()
        else:
            session = get_current_user()
            print(f"[CYBERCOM] Validating for user {session.id}, challenge {challenge.id}")

            # Find active container for this user + challenge
            tracker = DockerChallengeTracker.query.filter_by(
                user_id=session.id,
                docker_image=challenge.docker_image
            ).first()

        # STEP 2: Lookup flag by container_id (O(1) via UNIQUE index)
        if not tracker:
            print(f"[CYBERCOM] No active container found - checking static flags")

            # Fallback to static flags if no container exists
            flags = Flags.query.filter_by(challenge_id=challenge.id).all()
            for flag in flags:
                if get_flag_class(flag.type).compare(flag, submission):
                    print(f"[CYBERCOM] ✅ Static flag correct!")
                    return True, "Correct"

            print(f"[CYBERCOM] ❌ No matching flags")
            return False, "Incorrect"

        # Lookup flag by container_id (single query, O(1) performance)
        flag_mapping = DynamicFlagMapping.query.filter_by(
            container_id=tracker.instance_id
        ).first()

        if not flag_mapping:
            print(f"[CYBERCOM] Container {tracker.instance_id[:12]} has no flag - checking static flags")

            # Fallback to static flags
            flags = Flags.query.filter_by(challenge_id=challenge.id).all()
            for flag in flags:
                if get_flag_class(flag.type).compare(flag, submission):
                    print(f"[CYBERCOM] ✅ Static flag correct!")
                    return True, "Correct"

            return False, "Incorrect"

        # STEP 3: Decrypt flag
        try:
            expected_flag = decrypt_flag(flag_mapping.encrypted_flag)
        except Exception as e:
            print(f"[CYBERCOM ERROR] Decryption failed: {e}")
            return False, "Internal error - please contact admin"

        # STEP 4: Constant-time comparison (prevents timing attacks)
        print(f"[CYBERCOM] Comparing submission with flag for container {tracker.instance_id[:12]}")

        if not constant_time_compare(submission, expected_flag):
            print(f"[CYBERCOM] ❌ Incorrect flag")
            return False, "Incorrect"

        # Success - no state updates needed (stateless validation)
        print(f"[CYBERCOM] ✅ Correct flag for container {tracker.instance_id[:12]}!")
        return True, "Correct! CYBERCOM approved!"

    @staticmethod
    def solve(user, team, challenge, request):
        """
		This method is used to insert Solves into the database in order to mark a challenge as solved.
		Also deactivates the dynamic flag mapping for this instance.

		:param team: The Team object from the database
		:param chal: The Challenge object from the database
		:param request: The request the user submitted
		:return:
		"""
        data = request.form or request.get_json()
        submission = data["submission"].strip()
        docker = DockerConfig.query.filter_by(id=1).first()
        try:
            if is_teams_mode():
                docker_containers = DockerChallengeTracker.query.filter_by(
                    docker_image=challenge.docker_image).filter_by(team_id=team.id).first()
            else:
                docker_containers = DockerChallengeTracker.query.filter_by(
                    docker_image=challenge.docker_image).filter_by(user_id=user.id).first()

            # CYBERCOM: No state updates needed (stateless system)
            # Flag validation already occurred in attempt() method
            # Just clean up container
            delete_container(docker, docker_containers.instance_id)
            DockerChallengeTracker.query.filter_by(instance_id=docker_containers.instance_id).delete()
        except:
            pass
        solve = Solves(
            user_id=user.id,
            team_id=team.id if team else None,
            challenge_id=challenge.id,
            ip=get_ip(req=request),
            provided=submission,
        )
        db.session.add(solve)
        db.session.commit()
        # trying if this solces the detached instance error...
        #db.session.close()

    @staticmethod
    def fail(user, team, challenge, request):
        """
		This method is used to insert Submissions into the database in order to mark an answer incorrect.

		:param team: The Team object from the database
		:param chal: The Challenge object from the database
		:param request: The request the user submitted
		:return:
		"""
        data = request.form or request.get_json()
        submission = data["submission"].strip()
        wrong = Submissions(
            user_id=user.id,
            team_id=team.id if team else None,
            challenge_id=challenge.id,
            ip=get_ip(request),
            provided=submission,
        )
        db.session.add(wrong)
        db.session.commit()
        #db.session.close()


class DockerChallenge(Challenges):
    __mapper_args__ = {'polymorphic_identity': 'docker'}
    id = db.Column(None, db.ForeignKey('challenges.id'), primary_key=True)
    docker_image = db.Column(db.String(128), index=True)
    flag_template = db.Column(db.String(512), default="default_<hex>", index=True)


# API
container_namespace = Namespace("container", description='Endpoint to interact with containers')


@container_namespace.route("", methods=['POST', 'GET'])
class ContainerAPI(Resource):
    @authed_only
    # I wish this was Post... Issues with API/CSRF and whatnot. Open to a Issue solving this.
    def get(self):
        container = request.args.get('name')
        if not container:
            return abort(403, "No container specified")
        challenge = request.args.get('challenge')
        if not challenge:
            return abort(403, "No challenge name specified")
        challenge_id = request.args.get('challenge_id')
        if not challenge_id:
            return abort(403, "No challenge ID specified")
        
        docker = DockerConfig.query.filter_by(id=1).first()
        containers = DockerChallengeTracker.query.all()
        if container not in get_repositories(docker, tags=True):
            return abort(403,f"Container {container} not present in the repository.")
        if is_teams_mode():
            session = get_current_team()
            # First we'll delete all old docker containers (+2 hours)
            for i in containers:
                if int(session.id) == int(i.team_id) and (unix_time(datetime.utcnow()) - int(i.timestamp)) >= 7200:
                    delete_container(docker, i.instance_id)
                    DockerChallengeTracker.query.filter_by(instance_id=i.instance_id).delete()
                    db.session.commit()
            check = DockerChallengeTracker.query.filter_by(team_id=session.id).filter_by(docker_image=container).first()
        else:
            session = get_current_user()
            for i in containers:
                if int(session.id) == int(i.user_id) and (unix_time(datetime.utcnow()) - int(i.timestamp)) >= 7200:
                    delete_container(docker, i.instance_id)
                    DockerChallengeTracker.query.filter_by(instance_id=i.instance_id).delete()
                    db.session.commit()
            check = DockerChallengeTracker.query.filter_by(user_id=session.id).filter_by(docker_image=container).first()
        
        # If this container is already created, we don't need another one.
        if check != None and not (unix_time(datetime.utcnow()) - int(check.timestamp)) >= 300:
            return abort(403,"To prevent abuse, dockers can be reverted and stopped after 5 minutes of creation.")
        # Delete when requested
        elif check != None and request.args.get('stopcontainer'):
            delete_container(docker, check.instance_id)
            if is_teams_mode():
                DockerChallengeTracker.query.filter_by(team_id=session.id).filter_by(docker_image=container).delete()
            else:
                DockerChallengeTracker.query.filter_by(user_id=session.id).filter_by(docker_image=container).delete()
            db.session.commit()
            return {"result": "Container stopped"}
        # The exception would be if we are reverting a box. So we'll delete it if it exists and has been around for more than 5 minutes.
        elif check != None:
            delete_container(docker, check.instance_id)
            if is_teams_mode():
                DockerChallengeTracker.query.filter_by(team_id=session.id).filter_by(docker_image=container).delete()
            else:
                DockerChallengeTracker.query.filter_by(user_id=session.id).filter_by(docker_image=container).delete()
            db.session.commit()
        
        # Check if a container is already running for this user. We need to recheck the DB first
        containers = DockerChallengeTracker.query.all()
        for i in containers:
            if int(session.id) == int(i.user_id):
                return abort(403,f"Another container is already running for challenge:<br><i><b>{i.challenge}</b></i>.<br>Please stop this first.<br>You can only run one container.")

        # === CYBERCOM: SIMPLIFIED FLAG GENERATION ===

        # Get challenge to access flag template
        docker_challenge = DockerChallenge.query.filter_by(id=challenge_id).first()
        flag = None

        if docker_challenge:
            # STEP 1: Delete any old flags for this user+challenge
            # Simple DELETE (no complex state transitions)
            if is_teams_mode():
                deleted_count = DynamicFlagMapping.query.filter_by(
                    team_id=session.id,
                    challenge_id=challenge_id
                ).delete()
                if deleted_count > 0:
                    print(f"[CYBERCOM] Deleted {deleted_count} old flag(s) for challenge {challenge_id}, team {session.id}")
            else:
                deleted_count = DynamicFlagMapping.query.filter_by(
                    user_id=session.id,
                    challenge_id=challenge_id
                ).delete()
                if deleted_count > 0:
                    print(f"[CYBERCOM] Deleted {deleted_count} old flag(s) for challenge {challenge_id}, user {session.id}")

            # STEP 2: Generate plaintext flag using template
            flag_template = docker_challenge.flag_template or "default_<hex>"
            print(f"[CYBERCOM] Challenge {challenge_id}, Template: '{flag_template}'")
            flag = generate_dynamic_flag(flag_template)
            print(f"[CYBERCOM] Generated flag: {redact_flag(flag)}")

        # STEP 3: Create container (to get container_id)
        # Wrapped in try-except for production-grade error handling
        try:
            portsbl = get_unavailable_ports(docker)
            create = create_container(docker, container, session.name, portsbl, flag=flag)

            # Safe port extraction from our own data structure
            try:
                config = json.loads(create[1])
                port_bindings = config.get('HostConfig', {}).get('PortBindings', {})
                ports = port_bindings.values() if port_bindings else []
            except Exception as e:
                print(f"[CYBERCOM ERROR] Failed to parse port configuration: {e}")
                ports = []

            # Validate Docker response before accessing 'Id'
            if 'Id' not in create[0]:
                error_msg = create[0].get('message', 'Unknown Docker error')
                print(f"[CYBERCOM ERROR] Container response missing Id: {error_msg}")
                raise Exception(f"Invalid Docker response: {error_msg}")

            container_id = create[0]['Id']
            print(f"[CYBERCOM] Container created: {container_id[:12]}")

            # STEP 4: Store Docker tracker (CRE-enhanced with 15-minute runtime)
            # Get runtime policy for this challenge (defaults: 15 min base, 15 min extensions, max 5)
            policy = RuntimePolicy.from_challenge(challenge_id)
            print(f"[CRE] Using runtime policy: {policy.base_runtime_seconds}s base, "
                  f"{policy.extension_increment_seconds}s per extension, max {policy.max_extensions} extensions")

            # Safe port string extraction with validation
            port_list = []
            for p in ports:
                if p and len(p) > 0 and isinstance(p[0], dict) and 'HostPort' in p[0]:
                    port_list.append(p[0]['HostPort'])

            ports_str = ','.join(port_list) if port_list else ''

            # Warn if ports were expected but none extracted
            if not ports_str and len(portsbl) > 0:
                print(f"[CYBERCOM WARNING] Container {container_id[:12]} created but no ports extracted (expected ports based on image)")

            entry = DockerChallengeTracker(
                team_id=session.id if is_teams_mode() else None,
                user_id=session.id if not is_teams_mode() else None,
                docker_image=container,
                timestamp=unix_time(datetime.utcnow()),
                revert_time=unix_time(datetime.utcnow()) + policy.base_runtime_seconds,  # CRE: 15 min (not 5 min)
                instance_id=container_id,
                ports=ports_str,
                host=str(docker.hostname).split(':')[0],
                challenge=challenge,
                # === CRE LIFECYCLE FIELDS ===
                extension_count=0,
                created_at=datetime.utcnow(),
                last_extended_at=None
            )
            db.session.add(entry)

        except Exception as e:
            # Production-grade error handling with audit trail
            print(f"[CYBERCOM ERROR] Container creation failed: {e}")
            import traceback
            print(f"[CYBERCOM DEBUG] Traceback: {traceback.format_exc()}")

            # Attempt to log failure event (with nested try-except to prevent double-failure)
            try:
                event = ContainerEvent(
                    user_id=session.id if not is_teams_mode() else None,
                    challenge_id=challenge_id,
                    action="failed_create",
                    timestamp=datetime.utcnow(),
                    event_metadata={
                        "error": str(e),
                        "docker_image": container,
                        "user_id": session.id
                    }
                )
                db.session.add(event)
                db.session.commit()
            except:
                pass  # Don't fail twice if audit logging fails

            return abort(500, "Container creation failed. Please try again or contact administrator.")

        # STEP 5: Encrypt and store flag mapping
        if flag and challenge_id:
            # Encrypt flag before storage
            encrypted = encrypt_flag(flag)

            flag_mapping = DynamicFlagMapping(
                # User/Team identification (mutually exclusive)
                user_id=session.id if not is_teams_mode() else None,
                team_id=session.id if is_teams_mode() else None,
                challenge_id=challenge_id,

                # Container binding (UNIQUE constraint - this is the lookup key)
                container_id=container_id,

                # Encrypted flag (decrypted only during validation)
                encrypted_flag=encrypted,

                # Audit trail
                created_at=datetime.utcnow(),

                # Key rotation support (future)
                encryption_key_id=1
            )
            db.session.add(flag_mapping)
            print(f"[CYBERCOM] Encrypted flag stored for {'team' if is_teams_mode() else 'user'} {session.id}, "
                  f"container {container_id[:12]}, challenge {challenge_id}")

        db.session.commit()

        # === CRE AUDIT LOG ===
        try:
            event = ContainerEvent(
                user_id=session.id if not is_teams_mode() else None,
                challenge_id=challenge_id,
                container_id=container_id,
                action="created",
                timestamp=datetime.utcnow(),
                event_metadata={
                    "docker_image": container,
                    "base_runtime_seconds": policy.base_runtime_seconds,
                    "expiry_time": entry.revert_time,
                    "flag_encrypted": True if flag else False
                }
            )
            db.session.add(event)
            db.session.commit()
            print(f"[CRE] Audit log: Container {container_id[:12]} created for challenge {challenge_id}")
        except Exception as e:
            print(f"[CRE ERROR] Failed to log creation event: {e}")
            # Non-critical - continue even if audit logging fails
            db.session.rollback()

        #db.session.close()
        return


active_docker_namespace = Namespace("docker", description='Endpoint to retrieve User Docker Image Status')


@active_docker_namespace.route("", methods=['POST', 'GET'])
class DockerStatus(Resource):
    """
	The Purpose of this API is to retrieve a public JSON string of all docker containers
	in use by the current team/user.
	"""

    @authed_only
    def get(self):
        docker = DockerConfig.query.filter_by(id=1).first()
        if is_teams_mode():
            session = get_current_team()
            tracker = DockerChallengeTracker.query.filter_by(team_id=session.id)
        else:
            session = get_current_user()
            tracker = DockerChallengeTracker.query.filter_by(user_id=session.id)
        data = list()
        for i in tracker:
            data.append({
                'id': i.id,
                'team_id': i.team_id,
                'user_id': i.user_id,
                'docker_image': i.docker_image,
                'timestamp': i.timestamp,
                'revert_time': i.revert_time,
                'instance_id': i.instance_id,
                'ports': i.ports.split(','),
                'host': str(docker.hostname).split(':')[0]
            })
        return {
            'success': True,
            'data': data
        }


docker_namespace = Namespace("docker", description='Endpoint to retrieve dockerstuff')


@docker_namespace.route("", methods=['POST', 'GET'])
class DockerAPI(Resource):
    """
	This is for creating Docker Challenges. The purpose of this API is to populate the Docker Image Select form
	object in the Challenge Creation Screen.
	"""

    @admins_only
    def get(self):
        docker = DockerConfig.query.filter_by(id=1).first()
        images = get_repositories(docker, tags=True, repos=docker.repositories)
        if images:
            data = list()
            for i in images:
                data.append({'name': i})
            return {
                'success': True,
                'data': data
            }
        else:
            return {
                       'success': False,
                       'data': [
                           {
                               'name': 'Error in Docker Config!'
                           }
                       ]
                   }, 400



def load(app):
    app.db.create_all()
    CHALLENGE_CLASSES['docker'] = DockerChallengeType

    # === START CRE CLEANUP WORKER ===
    cleanup_worker.start()
    print("[CRE] ✅ Cleanup worker started (interval=60s, thread=CRE-Cleanup)")

    @app.template_filter('datetimeformat')
    def datetimeformat(value, format='%Y-%m-%d %H:%M:%S'):
        return datetime.fromtimestamp(value).strftime(format)
    register_plugin_assets_directory(app, base_path='/plugins/docker_challenges/assets')
    define_docker_admin(app)
    define_docker_status(app)
    CTFd_API_v1.add_namespace(docker_namespace, '/docker')
    CTFd_API_v1.add_namespace(container_namespace, '/container')
    CTFd_API_v1.add_namespace(active_docker_namespace, '/docker_status')
    CTFd_API_v1.add_namespace(kill_container, '/nuke')
    # CRE extension API
    CTFd_API_v1.add_namespace(container_extension_namespace, '/api/v1/container')
    print("[CRE] ✅ Extension API endpoints registered (/api/v1/container/extend, /api/v1/container/status)")
