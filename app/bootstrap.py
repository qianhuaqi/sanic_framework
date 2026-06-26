def get_extension_modules():
    from lingshu.extensions import mongo, mysql, redis

    return [mysql, redis, mongo]


def get_feature_blueprints(config=None):
    from app.route import get_blueprints

    return get_blueprints(config)
