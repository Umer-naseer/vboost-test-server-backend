INDEX = (
    ('Produce', [
        {
            'url': '/clients/package/',
            'perm': 'clients.change_package',
            'image': 'images.png',
            'title': 'Create Videos',
        },
        {
            'url': '/reporting/report/',
            'perm': 'reporting.change_report',
            'image': 'report.png',
            'title': 'Reports',
        },
        {
            'url': '/offers/submission/',
            'perm': 'offers.change_submission',
            'image': 'submissions.png',
            'title': 'Submissions',
        },
        {
            'url': '/mailer/email/',
            'perm': 'mailer.change_email',
            'image': 'email.jpg',
            'title': 'Outgoing Emails',
        },
    ]),

    ('Manage', [
        {
            'url': '/packages/inspect/',
            'perm': 'clients.change_package',
            'image': 'images.png',
            'title': 'Inspect Packages',
        },
        {
            'url': '/clients/company/',
            'perm': 'clients.change_company',
            'image': 'companies.png',
            'title': 'Companies',
        },
        {
            'url': '/clients/campaign/',
            'perm': 'clients.change_campaign',
            'image': 'campaigns.png',
            'title': 'Campaigns',
        },
        {
            'url': '/clients/contact/',
            'perm': 'clients.change_contact',
            'image': 'contacts.png',
            'title': 'Contacts',
        },
        {
            'url': '/templates/template/',
            'perm': 'templates.change_template',
            'image': 'templates.png',
            'title': 'Templates',
        },
        {
            'url': '/reporting/reportform/',
            'perm': 'reporting.change_reportform',
            'image': 'report.png',
            'title': 'Report Forms',
        },
        {
            'url': '/reporting/schedule/',
            'perm': 'reporting.change_schedule',
            'image': 'report_schedule.png',
            'title': 'Report Schedule',
        },
        {
            'url': '/mailer/unsubscribedemail',
            'perm': 'mailer.change_unsubscribedemail',
            'image': 'unsubscribe.png',
            'title': 'Unsubscribed Emails',
        },
        {
            'url': '/packages/inspect/?status=bounced',
            'perm': 'clients.change_package',
            'image': 'unsubscribe.png',
            'title': 'Bounced Packages',
        },
        {
            'url': '/gallery/image',
            'perm': 'clients.change_package',
            'image': 'logo.png',
            'title': 'Gallery',
        },
        {
            'url': '/live/montagevideo/',
            'perm': 'clients.change_package',
            'image': 'video.png',
            'title': 'Montage Videos',
        },
        {
            'url': '/users/active/',
            'perm': 'auth.change_user',
            'image': 'users.png',
            'title': 'Active/ Deactive Users',
        },
    ]),

    ('Settings', [
        {
            'url': '/campaigns/campaigntype/',
            'perm': 'campaigns.change_template',
            'image': 'campaigns.png',
            'title': 'Campaign Types',
        },
        {
            'url': '/auth/user/',
            'perm': 'auth.change_user',
            'image': 'users.png',
            'title': 'Users',
        },
        {
            'url': '/clients/userproxy/',
            'perm': 'auth.change_user',
            'image': 'users.png',
            'title': 'Delete My Accounts',
        },
        {
            'url': '/auth/group/',
            'perm': 'auth.change_group',
            'image': 'roles.png',
            'title': 'Groups',
        }
    ]),

    ('Documentation', [{
        'url': '/documentation/',
        'perm': 'clients.change_package',
        'image': 'wiki.png',
        'title': 'Documentation'
    }]),
)


def index(request):
    """Index menu variable."""

    menu = []

    for group, items in INDEX:
        items = list(filter(
            lambda item: request.user.has_perm(item['perm']),
            items))

        if items:
            menu.append([group, items])

    return {
        'index': menu,
    }
