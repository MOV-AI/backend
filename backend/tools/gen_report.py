"""
    Generate a report and send it to all interested users
"""

import os
import re
import datetime
import argparse
import smtplib
import requests
import json
from types import SimpleNamespace, MethodType as Method
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from movai_core_shared.logger import Log

from dal.scopes.fleetrobot import FleetRobot
from dal.scopes.robot import Robot
from dal.models.scopestree import scopes
from dal.models.var import Var


LOGGER = Log.get_logger(__name__)

# YYYY-MM-DDThh:mm:ss
# year is optional
# time is optional
# seconds is optional
_RE_TIME = re.compile(
    r"((?P<year>[0-9]{4})-)?(?P<month>[0-9]{2})-(?P<day>[0-9]{2})(.(?P<hour>[0-9]{2}):(?P<minute>[0-9]{2})(:(?P<second>[0-9]+))?)?$"
)
# delta time, everything is optional
# a single '-' means 'now' (no deltatime)
_RE_DELTA = re.compile(r"_((?P<weeks>[0-9]+)w)?((?P<days>[0-9]+)d)?((?P<hours>[0-9]+)h)?$")

_METRIC_MAP = dict()
""" Maps metrics names to generators """

_HTML_MAP = dict()
""" Maps metrics names to HTML sections
    Each section should have one '%s' to where the
    metric will go, str()'ed
"""

_CREDENTIALS = {"username": "admin"}


def get_today():
    return datetime.datetime.today()


def metric(metric_name, function=None):
    """Decorator to export a metric handler

    Handlers receive an instance of the FleetRobot
    to fetch metrics from and a namespace with timestamps:
    class Time:
        from: int
        to: int

    use as
    @metric(<metric_name>)
    def that_metric_handler(robot: FleetRobot, time: Time):
        # ...
    """
    if function is None:
        return Method(metric, metric_name)
    # else
    _METRIC_MAP[metric_name] = function
    _HTML_MAP[metric_name] = f"<li>{metric_name}: %s</li>"
    return function


#                                  #
# --------              -----------#
#   Space for metrics generators   #
# --------              -----------#
#                                  #

# @metric('<metric_name>')
# def metric_generator(robot: FleetRobot, time):
#   ...

# # or
# metric('<metric_name', callback_handler)


@metric("Total number of alert")
def alerts_total(robot, time):
    try:
        log_dict = get_logs_dict(robot.IP, time, limit=1)
    except Exception as e:
        LOGGER.warning(str(e))
        return None  # empty
    return log_dict["count"]


@metric("Total number of times emergency button was pressed")
def pressed_emergency_total(robot, time):
    return len(retrive_logs_given_event("EMERGENCY_PRESSED", robot, time))


@metric("Total number of succeeded recoveries")
def success_recovery_total(robot, time):
    return len(retrive_logs_given_event("RECOVERY_SUCCESS", robot, time))


@metric("Total number of failed recoveries")
def fail_recovery_total(robot, time):
    return len(retrive_logs_given_event("RECOVERY_FAILED", robot, time))


@metric("Total number of human interventions")
def human_intervation_total(robot, time):
    try:
        pressed = pressed_emergency_total(robot, time)
        succeeded = success_recovery_total(robot, time)
        failed = fail_recovery_total(robot, time)
    except Exception as e:
        LOGGER.warning(str(e))
        return None  # empty
    return pressed + succeeded + failed


@metric("Total number of carts")
def number_carts_total(robot, time):
    return get_delivered_carts(robot, time)


@metric("Total number of carts lost")
def number_carts_lost_total(robot, time):
    try:
        # TODO
        pass
    except Exception as e:
        LOGGER.warning(str(e))
        return None  # empty
    return 0


@metric("Time charging")
def charging_time(robot, time):
    try:
        start_times = retrive_logs_given_event("START_CHARGING", robot, time)
        stop_times = retrive_logs_given_event("STOP_CHARGING", robot, time)
    except Exception as e:
        LOGGER.warning(str(e))
        return None  # empty
    return (
        stop_times[0]["time"] - start_times[0]["time"]
        if len(start_times) > 0 and len(stop_times) > 0
        else 0
    )


@metric("Time operating")
def operating_time(robot, time):
    try:
        start_times = retrive_logs_given_event("START_OPERATING", robot, time)
        stop_times = retrive_logs_given_event("STOP_OPERATING", robot, time)
    except Exception as e:
        LOGGER.warning(str(e))
        return None  # empty
    return (
        stop_times[0]["time"] - start_times[0]["time"]
        if len(start_times) > 0 and len(stop_times) > 0
        else 0
    )


def create_metric_from_event(title, event):
    @metric(title)
    def inner(robot, time):
        return len(retrive_logs_given_event(event, robot, time))

    return inner


def retrive_logs_given_event(event, robot, time):
    try:
        logs_data = get_logs(robot.IP, time)
        event_logs = [
            x
            for x in logs_data
            if "event" in x and x["event"] == event and (time.t_from <= x["time"] < time.t_to)
        ]
    except Exception as e:
        LOGGER.warning(str(e))
        return None  # empty
    return event_logs


_EVENTS = [
    {"title": "Number of times pick-up was empty", "event": "PICKUP_EMPTY"},
    {
        "title": "Number of times “get task” didn’t return a “pick-up to drop-off” task",
        "event": "NO_TASKS",
    },
    {"title": "Number of alerts due to obstacles", "event": "OBSTACLE_FOUND"},
    {"title": "Number of gripper fails", "event": "GRIPPER_FAILED"},
    {"title": "Number of blocked pick-ups", "event": "PICKUP_BLOCKED"},
    {"title": "Number of full drops", "event": "DROP_FULL"},
    {"title": "Number of blocked drops", "event": "DROP_BLOCKED"},
    {"title": "Number of docking retries failed", "event": "DOCK_FAILED"},
    {"title": "Robot is not charging", "event": "NOT_CHARGING"},
    {"title": "Number of failed to release the cart", "event": "RELEASE_CART_FAILED"},
    {"title": "Number of cart in pickup not OK", "event": "CART_NOT_OK"},
]
for event in _EVENTS:
    create_metric_from_event(event["title"], event["event"])


@metric("Travel distance / day (meters)")
def travel_distance_day(robot, time):
    try:
        robot_var = Var("Fleet", robot.RobotName)
    except Exception as e:
        LOGGER.warning(str(e))
        return None  # empty
    return robot_var.kms_today * 1000


def get_delivered_carts(robot, time):
    list_of_deliveries = get_health_metrics(robot.IP, time, "numberOfDeliveries")["data"]
    return len(
        list(
            filter(
                lambda m: m["v"] == 1 and (time.t_from <= m["time"] < time.t_to),
                list_of_deliveries,
            )
        )
    )


def get_logs(ip, time, limit=100):
    return get_logs_dict(ip, time, limit)["data"]


def get_logs_dict(ip, time, limit=100):
    try:
        token = get_token(ip)
        endpoint = f"https://{ip}:5004/api/v1/logs/?limit={limit}&tags=ui&from={time.t_from}&to={time.t_to}&levels=ERROR,CRITICAL,INFO"
        headers = {
            "Content-Type": "application/javascript",
            "Authorization": f"bearer {token}",
        }
        response = requests.request("GET", endpoint, headers=headers, data={})
        response.raise_for_status()
    except requests.HTTPError as e:
        LOGGER.warning(str(e))
        return None  # empty
    data_dict = response.json()
    return data_dict


def get_token(ip):
    url = f"https://{ip}:5004/token-auth/"
    payload = {
        "username": _CREDENTIALS["username"],
        "password": _CREDENTIALS["password"],
    }
    headers = {"Content-Type": "application/json"}
    response = requests.request("POST", url, headers=headers, data=json.dumps(payload))
    return response.json()["access_token"]


def get_health_metrics(ip, time, name, limit=100):
    try:
        token = get_token(ip)
        endpoint = f"https://{ip}:5004/api/v1/metrics/?limit={limit}&name={name}&from={time.t_from}&to={time.t_to}"
        headers = {
            "Content-Type": "application/javascript",
            "Authorization": f"bearer {token}",
        }
        response = requests.request("GET", endpoint, headers=headers, data={})
        response.raise_for_status()
    except requests.HTTPError as e:
        LOGGER.warning(str(e))
        return None  # empty
    data_dict = response.json()
    return data_dict


#
# HTML MAPS
#
_HTML_BASE = (
    # TODO include date?
    # will get concatenated (and minified)
    "<html>"
    "<head></head>"  # insert style if necessary
    "<body>"
    f"<h3>Mov.ai Status Report {str(get_today())[0:10]}</h3>"
    "%s"  # robot's content go here
    "</body>"
    "</html>"
)


# insert robot name and content
_HTML_ROBOT_BASE = "<div><h4>Report for %s</h4><ul>%s</ul></div>"


# CSV is built based on metrics names
def get_raw_metrics(time):
    """
    Get/generate metrics for all robots
    returns a dict[ robot_name -> dict[metric -> value] ]
    """
    return {
        robot.RobotName: {
            metric_name: metric_generator(robot, time)
            for metric_name, metric_generator in _METRIC_MAP.items()
        }
        for robot in (FleetRobot(name) for name in Robot.get_all())
        if robot.RobotName is not None
    }


def build_html(data, time):
    """
    Builds the HTML message from template and data
    """
    # for metric in robot
    #   body.append(metric_map(metric))
    # for robot in robots
    #  fullbody.append(body)

    # build body for robots from metrics list
    # build body for html frmo robots bodies
    return _HTML_BASE % (
        str.join(
            "",
            (
                _HTML_ROBOT_BASE
                % (
                    robot_name,
                    str.join(
                        "",
                        (_HTML_MAP[name] % str(value) for name, value in metrics.items()),
                    ),
                )
                for robot_name, metrics in data.items()
            ),
        )
    )


def build_csv(data, time):
    """
    Builds the CSV attachment message from template and data
    """
    # header -> RobotName,*metric_names
    # lines -> <robot_name>,*metric_values

    return (
        str.join(
            "\r\n",
            (
                # header
                str.join(
                    ",",
                    ("Date", "Start time", "Finish time", "Robot", *_METRIC_MAP.keys()),
                ),
                # lines
                *(
                    str.join(
                        ",",
                        (
                            str(get_today())[0:10],
                            str(time.t_from),
                            str(time.t_to),
                            robot_name,
                            *(str(val) for val in metrics.values()),
                        ),
                    )
                    for robot_name, metrics in data.items()
                ),
            ),
        )
        + "\r\n"
    )  # extra final new line


def build_email(time, csv_name="report.csv"):
    """Build email
    only packages MIME parts
    no From/To/Subject ...
    add later
    """
    data = get_raw_metrics(time)
    html = build_html(data, time)
    csv = build_csv(data, time)

    mail = MIMEMultipart()

    html_body = MIMEText(html, "html")
    csv_attx = MIMEText(csv, "csv")
    csv_attx.add_header("Content-Disposition", "attachment; filename=%s" % csv_name)
    mail.attach(html_body)
    mail.attach(csv_attx)

    return mail


def send_report(args, dry=False):  # pylint: disable=redefined-outer-name
    """
    Get list of interested users,
    prepare report and send it to them
    """

    # receivers
    mail_to = list()
    users = scopes().list_scopes(scope="User")
    for user in users:
        user_obj = scopes().User[user["ref"]]
        if user_obj.SendReport and user_obj.Email is not None:
            mail_to.append(user_obj.Email)

    if len(mail_to) == 0:
        # we got no one interested in reports
        LOGGER.info("No user has the 'SendReport' flag and/or 'Email' set")
        return 0

    subject_name = f"{args.subject} {str(get_today())[0:10]}"
    csv_name = subject_name + ".csv"
    time_interval = SimpleNamespace(t_from=args.time_from, t_to=args.time_to)
    if dry:
        data = get_raw_metrics(time_interval)
        csv_str = build_csv(data, time_interval)
        with open(csv_name, mode="w") as f:
            f.write(csv_str)
        print(f"Report in {csv_name}")
    else:
        mail = build_email(time_interval, csv_name)
        mail["From"] = args.smtp_email
        mail["Subject"] = subject_name
        mail["To"] = str.join(", ", mail_to)
        send_mail(args, mail)
        print(f"Report was sent to {mail_to}")


def send_mail(args, mail):
    mail_raw = mail.as_string()
    # connect and set
    try:
        with smtplib.SMTP(host=args.smtp_host, port=args.smtp_port) as client:
            client.starttls()
            client.login(args.smtp_user, args.smtp_pass)
            ret = client.sendmail(mail["From"], mail["To"], mail_raw)
            # print ret
            for entry, cause in ret.items():
                LOGGER.error("Failed to send email to '%s': %s", entry, cause)
    except smtplib.SMTPException as e:
        LOGGER.error("Failed to send report", e)


def _from_timestamp(iso, base):
    m = _RE_TIME.match(iso)
    if m is None:
        return None

    parts = m.groupdict()
    # update parts
    sane_parts = {k: int(v) if v is not None else getattr(base, k) for k, v in parts.items()}
    return datetime.datetime(**sane_parts)


def _from_delta(iso, base):
    m = _RE_DELTA.match(iso)
    if m is None:
        return None

    parts = {k: int(v) if v is not None else 0 for k, v in m.groupdict().items()}

    return base - datetime.timedelta(**parts)


def main():
    parser = argparse.ArgumentParser("gen_report")
    # SMTP_HOST, SMTP_USER, SMTP_PASS, SMTP_EMAIL, SMTP_PORT
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_email = os.getenv("SMTP_EMAIL")
    parser.add_argument(
        "-su",
        "--smtp-user",
        help="SMTP authentication username",
        metavar="SMTP_USER",
        default=smtp_user,
        required=smtp_user is None,
    )
    parser.add_argument(
        "-sp",
        "--smtp-pass",
        help="SMTP authentication password",
        metavar="SMTP_PASS",
        default=smtp_pass,
        required=smtp_pass is None,
    )
    parser.add_argument(
        "-sH",
        "--smtp-host",
        help="SMTP Host/IP",
        metavar="SMTP_HOST",
        default=smtp_host,
        required=smtp_host is None,
    )
    parser.add_argument(
        "-sP",
        "--smtp-port",
        help="SMTP Host Port",
        metavar="SMTP_PORT",
        default=smtp_port,
    )
    parser.add_argument(
        "-se",
        "--smtp-email",
        help="SMTP sender email",
        metavar="SMTP_EMAIL",
        default=smtp_email,
        required=smtp_email is None,
    )
    parser.add_argument(
        "-s",
        "--subject",
        help="Email subject",
        metavar="SUBJECT",
        default="Mov.ai Status Report",
    )
    parser.add_argument(
        "-tf",
        "--time-from",
        help="Datetime in ISO format (YYYY-MM-DDThh:mm:ss) or delta (-[#w][#d][#m]). Default is 1 day before now (-1d). Check regex for more info.",
        default="_1d",
    )
    parser.add_argument(
        "-tt",
        "--time-to",
        help="Datetime in ISO format (YYYY-MM-DDThh:mm:ss) or delta (-[#w][#d][#m]). Default is now. Check regex for more info.",
        default="_",
    )
    parser.add_argument(
        "-mu",
        "--movai-username",
        help="mov.ai username",
        default=_CREDENTIALS["username"],
    )
    parser.add_argument(
        "-mp",
        "--movai-password",
        help="mov.ai user password",
    )
    parser.add_argument(
        "-d",
        "--dry",
        "--dry-run",
        dest="dry",
        action="store_true",
        help="Don't send email just create csv",
    )

    args = parser.parse_args()
    args.smtp_port = int(args.smtp_port)

    # update default credentials
    _CREDENTIALS["username"] = args.movai_username
    _CREDENTIALS["password"] = args.movai_password

    # handle times
    now = get_today()
    # time-to
    if args.time_to[0] == "_":
        time = _from_delta(args.time_to, now)
        if time is None:
            LOGGER.error("Invalid delta time '%s'", args.time_to)
            exit(1)
    else:
        time = _from_timestamp(args.time_to, now)
        if time is None:
            LOGGER.error("Invalid ISO date '%s'", args.time_to)
            exit(1)
    args.time_to = int(time.timestamp())
    # time-from
    if args.time_from[0] == "_":
        time = _from_delta(args.time_from, now)
        if time is None:
            LOGGER.error("Invalid delta time '%s'", args.time_from)
    else:
        time = _from_timestamp(args.time_from, now)
        if time is None:
            LOGGER.error("Invalid ISO date '%s'", args.time_from)
    args.time_from = int(time.timestamp())

    send_report(args, dry=args.dry)


if __name__ == "__main__":
    main()
