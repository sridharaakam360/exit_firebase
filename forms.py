from flask_wtf import FlaskForm
from wtforms import StringField, FloatField, TextAreaField, SelectField, IntegerField, SubmitField, PasswordField, RadioField, BooleanField
from wtforms.validators import DataRequired, Length, Regexp, Optional, Email, NumberRange

class LoginTypeForm(FlaskForm):
    login_type = RadioField('Login Type', choices=[
        ('individual', 'Individual Login'), 
        ('institution', 'Institution Admin'), 
        ('student', 'Institution Student')
    ], validators=[DataRequired()])
    submit = SubmitField('Continue')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=50)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=50)])
    submit = SubmitField('Login')

class InstitutionLoginForm(FlaskForm):
    institution_code = StringField('Institution Code', validators=[DataRequired(), Length(min=6, max=20)])
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=50)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=50)])
    submit = SubmitField('Login')

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=50)])
    email = StringField('Email', validators=[DataRequired(), Regexp(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', message='Invalid email address')])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=50)])
    submit = SubmitField('Register')

class InstitutionRegisterForm(FlaskForm):
    institution_name = StringField('Institution Name', validators=[DataRequired(), Length(min=2, max=100)])
    admin_name = StringField('Admin Name', validators=[DataRequired(), Length(min=2, max=100)])
    email = StringField('Email Address', validators=[DataRequired(), Regexp(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', message='Invalid email address')])
    username = StringField('Admin Username', validators=[DataRequired(), Length(min=4, max=50)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=50)])
    submit = SubmitField('Register')

class StudentRegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=50)])
    email = StringField('Email', validators=[DataRequired(), Regexp(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', message='Invalid email address')])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=50)])
    institution_code = StringField('Institution Code', validators=[DataRequired(), Length(min=6, max=20)])
    submit = SubmitField('Register as Student')

class QuestionForm(FlaskForm):
    question = TextAreaField('Question', validators=[DataRequired()])
    option_a = StringField('Option A', validators=[DataRequired()])
    option_b = StringField('Option B', validators=[DataRequired()])
    option_c = StringField('Option C', validators=[DataRequired()])
    option_d = StringField('Option D', validators=[DataRequired()])
    correct_answer = SelectField('Correct Answer', 
                               choices=[('a', 'A'), ('b', 'B'), ('c', 'C'), ('d', 'D')], 
                               validators=[DataRequired()])
    chapter = StringField('Chapter', validators=[DataRequired()])
    difficulty = SelectField('Difficulty', 
                           choices=[('easy', 'Easy'), ('medium', 'Medium'), ('hard', 'Hard')], 
                           validators=[DataRequired()])
    degree = SelectField('Degree', 
                        choices=[('', 'All Degrees'), ('bpharm', 'B.Pharm'), ('dpharm', 'D.Pharm')], 
                        validators=[DataRequired()])
    subject_id = SelectField('Subject', coerce=int, validators=[DataRequired()])
    is_previous_year = BooleanField('Previous Year Question')
    previous_year = StringField('Previous Year', validators=[Optional()])
    topics = StringField('Topics (comma-separated)')
    explanation = TextAreaField('Explanation', validators=[DataRequired()])
    submit = SubmitField('Submit')

class UserForm(FlaskForm):
    username = StringField('Username', validators=[
        DataRequired(),
        Length(min=3, max=50),
        Regexp('^[a-zA-Z0-9_]+$', message='Username can only contain letters, numbers, and underscores')
    ])
    email = StringField('Email', validators=[
        DataRequired(),
        Length(max=120),
        Regexp(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', message='Invalid email address')
    ])
    password = PasswordField('Password', validators=[
        Optional(),
        Length(min=6, message='Password must be at least 6 characters long')
    ])
    role = SelectField('Role', choices=[
        ('superadmin', 'Super Admin'),
        ('instituteadmin', 'Institute Admin'),
        ('individual', 'Individual User'),
        ('student', 'Student')
    ], validators=[DataRequired()])
    status = SelectField('Status', choices=[
        ('active', 'Active'),
        ('inactive', 'Inactive')
    ], validators=[DataRequired()])
    submit = SubmitField('Add User')

class AddStudentForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[Optional(), Length(min=6)])
    institution_code = StringField('Institution Code', validators=[Optional()])
    submit = SubmitField('Add Student')

class SubscriptionForm(FlaskForm):
    payment_method = RadioField(
        'Payment Method',
        choices=[('credit_card', 'Credit Card'), ('debit_card', 'Debit Card'), ('upi', 'UPI')],
        validators=[DataRequired()]
    )
    submit = SubmitField('Subscribe')

class AddPlanForm(FlaskForm):
    name = StringField('Plan Name', validators=[DataRequired()])
    price = FloatField('Price', validators=[DataRequired(), NumberRange(min=0)])
    duration_months = IntegerField('Duration (Months)', validators=[DataRequired(), NumberRange(min=1)])
    degree_access = SelectField('Degree Access', choices=[('both', 'Both'), ('Dpharm', 'DPharm'), ('Bpharm', 'BPharm')], validators=[DataRequired()])
    is_institution = BooleanField('Institutional Plan')
    student_range = IntegerField('Student Range', validators=[NumberRange(min=1)], default=None)
    custom_student_range = BooleanField('Custom Student Range')
    description = TextAreaField('Description')
    submit = SubmitField('Add Plan')