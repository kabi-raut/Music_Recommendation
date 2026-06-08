from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
import re

class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(required=False, label='Full name')

    class Meta:
        model = User
        fields = ["username","first_name", "email", "password1", "password2"]

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if username and username[0].isdigit():
            raise forms.ValidationError('Username cannot start with a number.')
        return username

    def clean_first_name(self):
        full_name = self.cleaned_data.get('first_name', '').strip()
        if full_name and not re.fullmatch(r'[A-Za-z ]+', full_name):
            raise forms.ValidationError('Full name must contain only letters and spaces.')
        return full_name


class UserProfileForm(forms.ModelForm):
    first_name = forms.CharField(required=False, label='Full name')
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ["username", "first_name", "email"]

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if username and username[0].isdigit():
            raise forms.ValidationError('Username cannot start with a number.')

        if User.objects.exclude(pk=self.instance.pk).filter(username__iexact=username).exists():
            raise forms.ValidationError('This username is already taken.')
        return username

    def clean_first_name(self):
        full_name = self.cleaned_data.get('first_name', '').strip()
        if full_name and not re.fullmatch(r'[A-Za-z ]+', full_name):
            raise forms.ValidationError('First name must contain only letters and spaces.')
        return full_name

    def save(self, commit=True):
        user = super().save(commit=False)
        user.last_name = ''
        if commit:
            user.save()
        return user


class ForgotPasswordRequestForm(forms.Form):
    email = forms.EmailField(
        required=True,
        label='Email address',
        widget=forms.EmailInput(attrs={'placeholder': 'Enter your account email'}),
    )


class OTPVerificationForm(forms.Form):
    otp = forms.CharField(
        required=True,
        min_length=6,
        max_length=6,
        label='OTP code',
        widget=forms.TextInput(attrs={'placeholder': 'Enter 6-digit OTP', 'autocomplete': 'one-time-code'}),
    )

    def clean_otp(self):
        otp = (self.cleaned_data.get('otp') or '').strip()
        if not otp.isdigit():
            raise forms.ValidationError('OTP must contain exactly 6 digits.')
        return otp
