from behave_toolkit import install


def before_all(context):
    install(context, "examples/behave-toolkit.yaml")
