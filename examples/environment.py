from behave_toolkit import activate_feature_scope, activate_scenario_scope, install


def before_all(context):
    install(context, "examples/behave-toolkit.yaml")


def before_feature(context, feature):
    del feature
    activate_feature_scope(context)


def before_scenario(context, scenario):
    del scenario
    activate_scenario_scope(context)
