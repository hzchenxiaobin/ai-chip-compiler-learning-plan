"""账号视图：注册 / 登录 / 登出 / CSRF 失败提示。

登录接口使用 Redis 缓存做简单限流（每 IP 10 次/5 分钟）；
会话 Cookie 由 settings 统一配置（HttpOnly / SameSite=Lax）。
"""
from django.contrib.auth import login as auth_login, logout as auth_logout
from django.contrib.auth.views import LoginView
from django.core.cache import cache
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .forms import LoginForm, RegisterForm

_LOGIN_LIMIT = 10
_LOGIN_WINDOW = 300


def _rate_limited(request) -> bool:
    """登录限流（Redis）。Redis 不可用时降级为不限流（设计文档 §9.4）。"""
    key = f"login-rate:{request.META.get('REMOTE_ADDR', 'unknown')}"
    try:
        count = cache.get(key, 0)
    except Exception:
        return False  # Redis 故障：放行（无缓存限流可用）。
    if count is None:
        count = 0
    if count >= _LOGIN_LIMIT:
        return True
    try:
        cache.set(key, count + 1, _LOGIN_WINDOW)
    except Exception:
        return False
    return False


class LoginView(LoginView):
    template_name = "accounts/login.html"
    form_class = LoginForm
    redirect_authenticated_user = True

    def post(self, request, *args, **kwargs):
        if _rate_limited(request):
            return render(
                request, self.template_name,
                {"form": self.form_class(), "rate_limited": True},
                status=429,
            )
        return super().post(request, *args, **kwargs)


@require_http_methods(["GET", "POST"])
def register(request):
    if request.user.is_authenticated:
        return redirect("/")
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            auth_login(request, user)
            return redirect("/")
    else:
        form = RegisterForm()
    return render(request, "accounts/register.html", {"form": form})


@require_http_methods(["POST"])
def logout_view(request):
    auth_logout(request)
    return redirect("/")


@require_http_methods(["GET", "POST"])
def change_password(request):
    """修改密码（当前密码校验 + 登出其他会话语义）。"""
    from django.contrib.auth import update_session_auth_hash
    from django.contrib.auth.forms import PasswordChangeForm

    if request.method == "POST":
        form = PasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, form.user)
            return redirect("/settings/#account")
    else:
        form = PasswordChangeForm(user=request.user)
    return render(request, "accounts/password_change.html", {"form": form})


@require_http_methods(["POST"])
def save_preferences(request):
    """账号偏好（accounts_profile.preferences，设计文档 §8.2）。"""
    from .models import Profile

    profile, _ = Profile.objects.get_or_create(user=request.user)
    preferences = dict(profile.preferences or {})
    preferences["account_emails"] = request.POST.get("account_emails") == "on"
    profile.preferences = preferences
    profile.save(update_fields=["preferences", "updated_at"])
    from django.contrib import messages

    messages.success(request, "偏好已保存。")
    return redirect("/settings/#preferences")


def csrf_failure(request, reason=""):
    import sys

    print(f"[csrf_failure] {reason}", file=sys.stderr)
    return HttpResponse(
        render(request, "accounts/csrf_failure.html", {"reason": reason}).content,
        status=403,
    )
