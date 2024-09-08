import random 
from django.core.mail import send_mail
from authenticator_user import settings
from .models import OneTimePassword, User

def generateOtp():
    otp = ""
    for i in range(6):
        otp += str(random.randint(1,9))
    return otp

def send_code_to_user(email, code):
    Subject = "One time passcode for Email verification"
    otp_code = generateOtp()
    print(f"Your OTP is {otp_code}")
    user = User.objects.get(email=email)
    current_site = "my.Auth.com"
    email_body = f"Hello {user.first_name},\n\nYour OTP is {otp_code}\n\nThank you for using our service\n\n{current_site}"
    from_email = settings.DEFAULT_FROM_EMAIL
    
    OneTimePassword.objects.create(user=user, otp=otp_code)
    
    d_email = send_mail(subject = Subject, body = email_body, from_email = from_email, to = [email])
    d_email.send(fail_silently = True)
    
    
    