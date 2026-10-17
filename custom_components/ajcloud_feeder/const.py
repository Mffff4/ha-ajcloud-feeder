"""Constants for the AJCloud Smart Pet Feeder integration."""

DOMAIN = "ajcloud_feeder"
NAME = "AJCloud Smart Pet Feeder"

DEFAULT_APP_NAME = "ajcloud"
DEFAULT_VENDOR_CODE = "AJC"
PORTAL_URL = "https://uac-portal.ajcloud.net/api/v1/account-node-query"

CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_REGION = "region"
CONF_DEVICE_ID = "device_id"
CONF_PORTIONS = "portions"

ATTR_FEEDER_ID = "feeder_id"
ATTR_PORTIONS = "portions"
ATTR_LAST_FEED_TIME = "last_feed_time"
ATTR_OUTLET = "outlet"
ATTR_MODEL = "model"
ATTR_FIRMWARE = "firmware"
ATTR_IP_ADDRESS = "ip_address"
ATTR_MAC_ADDRESS = "mac_address"

DEFAULT_PORTIONS = 1
MIN_PORTIONS = 1
MAX_PORTIONS = 10

SERVICE_FEED = "feed_portions"
