import json
import os.path
from base64 import b64encode

import requests
from django.conf import settings

IDOMOO_TOKEN_API_URI = '"https://usa-api.idomoo.com/api/v3/oauth/token"'
IDOMOO_API_URI = "https://usa-api.idomoo.com/api/v3/storyboards/generate"
IDOMOO_ACCOUNT_ID = 1970
IDOMOO_AUTH_TOKEN = "IuSZSeTpvYf7cefb2c7fed2a4ea56b301817cd35a3CgSsr1HYY7"


def get_basic_auth_token(username, password):
    token = b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def get_token():
    headers = {
        "Content-Type": "application/json",
        "Authorization": get_basic_auth_token(IDOMOO_ACCOUNT_ID, IDOMOO_AUTH_TOKEN),
    }

    response = requests.post(IDOMOO_TOKEN_API_URI, headers=headers).json()

    token_type = response["token_type"]
    access_token = response["access_token"]

    return f"{token_type} {access_token}"


def get_base_request(filename, storyboard_id):
    return {
        "response_format": "json",
        "storyboard_id": int(storyboard_id),
        "output": {"video": [{"format": "mp4", "height": 100}]},
        "data": [],
    }


def get_package_images(package, max_count, offset=0):
    images = list(package.images.all()[offset:max_count])
    # If number of images less than max_count, need to increase it
    # to max_count by doubling images from the beginning of their list
    count = max_count - offset
    if len(images) < count:
        number_to_add = count - len(images)
        for i in range(0, number_to_add):
            try:
                images.append(images[i])
            except IndexError:
                pass
    return images


def get_file_url(f):
    return os.path.join(
        settings.IDOMOO_HOST_URL,
        "media",
        str(f).lstrip("/"),
    )


def get_data_images(key, images):
    return [
        {
            "key": "{}{}".format(key, i + 1),
            "val": get_file_url(image.image),
        }
        for i, image in enumerate(images)
    ]


def get_drone_footage(package):
    campaign_image = package.campaign.images.order_by("id").first()
    if campaign_image:
        return get_file_url(campaign_image.image)
    return None


def get_final_video_or_drone_footage(package):
    media = package.campaign.media.filter(name="final_video").first()
    if media:
        return get_file_url(media.file), media.duration
    image = package.campaign.images.order_by("id").first()
    if image:
        return get_file_url(image.image), None
    return None, None


def get_intro_video(package):
    media = package.campaign.media.filter(name="intro_video").first()
    if media:
        return get_file_url(media.file), media.duration
    return None, None


def get_scene_duration(s, duration):
    from bisect import bisect

    if duration:
        i = bisect(s, duration, 0, len(s) - 1)
        return s[i]
    else:
        return s[0]


def get_data_mylead1(package, config={}):
    WELCOME_DURATIONS = [7, 11, 15]
    images = get_package_images(package, config.get("max_count", 0))
    drone_footage = get_drone_footage(package)
    welcome_video, welcome_duration = get_intro_video(package)
    welcome_dealer_video_duration = get_scene_duration(
        WELCOME_DURATIONS, welcome_duration
    )
    soundtrack = package.campaign.media.filter(name="soundtrack").first()
    return [
        {
            "key": "welcome_dealer_video_duration",
            "val": str(welcome_dealer_video_duration),
        },
        {
            "key": "welcome_dealer_video",
            "val": welcome_video,
        },
        {
            "key": "agency_title",
            "val": package.company.name,
        },
        {
            "key": "car_model",
            "val": "",
        },
        {
            "key": "customer_name",
            "val": package.contact.name,
        },
        {
            "key": "drone_duration",
            "val": "7",
        },
        {
            "key": "drone_footage",
            "val": drone_footage,
        },
        {
            "key": "soundtrack",
            "val": soundtrack and get_file_url(soundtrack.file) or "",
        },
        {
            "key": "user_photo_count",
            "val": str(len(images)),
        },
    ] + get_data_images("user_photo", images)


def get_data_myride1(package, config={}):
    DRONE_DURATIONS = [7, 10]
    images = get_package_images(package, config.get("max_count", 0))
    # Excluding drone_footage photo
    dealership_images = get_package_images(package, 3, 1)
    drone_footage, drone_duration = get_final_video_or_drone_footage(package)
    drone_duration = get_scene_duration(DRONE_DURATIONS, drone_duration)
    soundtrack = package.campaign.media.filter(name="soundtrack").first()
    welcome = package.campaign.text.filter(name="welcome").first()
    slogan = package.campaign.text.filter(name="slogan").first()
    return (
        [
            {
                "key": "welcome",
                "val": welcome and welcome.value or "",
            },
            {
                "key": "slogan",
                "val": slogan and slogan.value or "",
            },
            {
                "key": "agency_title",
                "val": package.company.name,
            },
            {
                "key": "customer_name",
                "val": package.contact.name,
            },
            {
                "key": "drone_duration",
                "val": str(drone_duration),
            },
            {
                "key": "drone_footage",
                "val": drone_footage,
            },
            {
                "key": "soundtrack",
                "val": soundtrack and get_file_url(soundtrack.file) or "",
            },
            {
                "key": "dealership_photo_count",
                "val": str(len(dealership_images)),
            },
            {
                "key": "user_photo_count",
                "val": str(len(images)),
            },
        ]
        + get_data_images("user_photo", images)
        + get_data_images("dealership_photo", dealership_images)
    )


def get_idomoo_request(package):
    storyboard_configs = {
        "idomoo_mylead1": {
            "storyboard_id": "14493",
            "max_count": 6,
            "func": get_data_mylead1,
        },
        "idomoo_myride1": {
            "storyboard_id": "15027",
            "max_count": 4,
            "func": get_data_myride1,
        },
    }
    template = package.campaign.get_video_template()
    storyboard_config = storyboard_configs.get(template)
    storyboard_id = storyboard_config["storyboard_id"]
    idomoo_request = get_base_request(str(package.id), storyboard_id)
    idomoo_request["data"] = storyboard_config["func"](package, storyboard_config)
    return idomoo_request


def push(package):
    idomoo_request = get_idomoo_request(package)
    headers = {
        "Content-Type": "application/json",
        "Content-Length": str(len(json.dumps(idomoo_request))),
        "Authorization": get_token(),
    }

    response = requests.post(
        IDOMOO_API_URI,
        headers=headers,
        data=json.dumps(idomoo_request),
    ).json()

    if response["check_status_url"] in ["ERROR", "NOT_EXIST"]:
        raise Exception("{}".format(response["check_status_url"]))

    # FIXME any possible errors and their handling?
    return response["output"]["video"][0]["links"]["url"]
