app_name = "elab_notebook"
app_title = "Elab Notebook"
app_publisher = "SHIVAM SINGH"
app_description = "This is experiment tracker app."
app_email = "shivam.singh@microcrispr.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "elab_notebook",
# 		"logo": "/assets/elab_notebook/logo.png",
# 		"title": "Elab Notebook",
# 		"route": "/elab_notebook",
# 		"has_permission": "elab_notebook.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/elab_notebook/css/elab_notebook.css"
# app_include_js = "/assets/elab_notebook/js/elab_notebook.js"

# include js, css files in header of web template
# web_include_css = "/assets/elab_notebook/css/elab_notebook.css"
# web_include_js = "/assets/elab_notebook/js/elab_notebook.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "elab_notebook/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# Prefills a new Stock Entry opened from a Lab Experiment run - see the file for
# why the entry cannot simply be created for the user instead.
doctype_js = {"Stock Entry": "public/js/stock_entry.js"}
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "elab_notebook/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "elab_notebook.utils.jinja_methods",
# 	"filters": "elab_notebook.utils.jinja_filters"
# }

# Installation
# ------------

before_install = "elab_notebook.install.before_install"
# after_install = "elab_notebook.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "elab_notebook.uninstall.before_uninstall"
# after_uninstall = "elab_notebook.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "elab_notebook.utils.before_app_install"
# after_app_install = "elab_notebook.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "elab_notebook.utils.before_app_uninstall"
# after_app_uninstall = "elab_notebook.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "elab_notebook.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# Employee Function is a shared master, so field-level scoping cannot isolate
# one employee's templates from another's. Isolation is owner-based and applied
# to both list/report queries and direct single-document access.
permission_query_conditions = {
	"Experiment Template": "elab_notebook.permissions.get_permission_query_conditions",
	# A team roster belongs to the Employee Function head who owns it.
	"Experiment Team": "elab_notebook.permissions.get_team_permission_query_conditions",
	"Lab Experiment": "elab_notebook.permissions.get_lab_experiment_permission_query_conditions",
	# Legacy Experiment keeps its isolation until it is retired - it still holds
	# data, and an unregistered doctype is readable by every Employee.
	"Experiment": "elab_notebook.permissions.get_experiment_permission_query_conditions",
	"Sample": "elab_notebook.permissions.get_sample_permission_query_conditions",
}

has_permission = {
	"Experiment Template": "elab_notebook.permissions.has_permission",
	"Experiment Team": "elab_notebook.permissions.has_team_permission",
	"Lab Experiment": "elab_notebook.permissions.has_lab_experiment_permission",
	"Experiment": "elab_notebook.permissions.has_experiment_permission",
	"Sample": "elab_notebook.permissions.has_sample_permission",
}

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# Lab Experiment carries these rules in its own controller
# (elab_notebook/doctype/lab_experiment/lab_experiment.py), so it needs no entry
# here. Legacy Experiment is a UI-created doctype with no controller file, so its
# gate stays attached through doc_events until the doctype is retired.
doc_events = {
	"Experiment": {
		"before_insert": "elab_notebook.experiment_access.validate_experiment_participant",
		"validate": "elab_notebook.experiment_access.validate_experiment_fields",
		"on_trash": "elab_notebook.experiment_access.validate_experiment_delete",
	},
}

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"elab_notebook.tasks.all"
# 	],
# 	"daily": [
# 		"elab_notebook.tasks.daily"
# 	],
# 	"hourly": [
# 		"elab_notebook.tasks.hourly"
# 	],
# 	"weekly": [
# 		"elab_notebook.tasks.weekly"
# 	],
# 	"monthly": [
# 		"elab_notebook.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "elab_notebook.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "elab_notebook.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "elab_notebook.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["elab_notebook.utils.before_request"]
# after_request = ["elab_notebook.utils.after_request"]

# Job Events
# ----------
# before_job = ["elab_notebook.utils.before_job"]
# after_job = ["elab_notebook.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"elab_notebook.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

