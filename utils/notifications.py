from flask_mail import Message
from flask import current_app

def notify_subscribers_of_plan_status(plan, users, institutions, action):
    for user in users:
        if user['subscription_plan_id'] == plan['id']:
            msg = Message(
                subject=f"Subscription Plan {action}",
                sender=current_app.config['MAIL_USERNAME'],
                recipients=[user['email']],
                body=f"Dear {user['username']},\n\nThe '{plan['name']}' plan has been {action.lower()}. "
                     f"You can continue using it until your subscription ends on {user['subscription_end']}. "
                     f"After that, you will be reassigned to the default plan.\n\nThank you,\nThe Team"
            )
            current_app.extensions['mail'].send(msg)
    for institution in institutions:
        if institution['subscription_plan_id'] == plan['id']:
            msg = Message(
                subject=f"Subscription Plan {action}",
                sender=current_app.config['MAIL_USERNAME'],
                recipients=[institution['email']],
                body=f"Dear {institution['name']},\n\nThe '{plan['name']}' plan has been {action.lower()}. "
                     f"Your institution can continue using it until {institution['subscription_end']}. "
                     f"After that, you will be reassigned to the default plan.\n\nThank you,\nThe Team"
            )
            current_app.extensions['mail'].send(msg)