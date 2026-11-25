"""账号表单：注册与登录（设计文档 §4、§9.3）。

只收集账号与会话所需字段：用户名/邮箱/密码；不采集真实姓名等无关信息。
"""
from django import forms
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User


class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        required=True, label="邮箱",
        help_text="仅用于账号找回等必要用途，不对外展示。",
    )

    class Meta:
        model = User
        fields = ("username", "email")

    def clean_username(self):
        username = self.cleaned_data["username"]
        if not username.isascii() or not 3 <= len(username) <= 30:
            raise forms.ValidationError("用户名须为 3—30 位字母数字。")
        return username


class LoginForm(AuthenticationForm):
    username = forms.CharField(label="用户名", max_length=30)
    password = forms.CharField(label="密码", widget=forms.PasswordInput)
