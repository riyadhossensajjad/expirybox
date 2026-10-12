from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from marketplace.models import Listing

from .forms import GlassPasswordChangeForm, LoginForm, ProfileForm, SignUpForm
from .models import User


def signup(request):
    if request.user.is_authenticated:
        return redirect("items:dashboard")
    form = SignUpForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        request.session["welcome"] = True
        messages.success(request, f"Welcome, {user.get_short_name()}. Add your first item to start tracking.")
        return redirect("items:create")
    return render(request, "accounts/signup.html", {"form": form})


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def form_valid(self, form):
        response = super().form_valid(form)
        self.request.session["welcome"] = True
        return response

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Show the demo login only when `seed_demo` has been run.
        ctx["show_demo_hint"] = User.objects.filter(email="ayesha@example.com").exists()
        return ctx


@require_POST
def logout_view(request):
    logout(request)
    messages.info(request, "You're signed out.")
    return redirect("home")


@login_required
def profile(request):
    profile_form = ProfileForm(instance=request.user)
    password_form = GlassPasswordChangeForm(request.user)

    if request.method == "POST":
        if "save_profile" in request.POST:
            profile_form = ProfileForm(request.POST, request.FILES, instance=request.user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Profile saved.")
                return redirect("accounts:profile")
        elif "change_password" in request.POST:
            password_form = GlassPasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Password changed.")
                return redirect("accounts:profile")

    return render(request, "accounts/profile.html", {
        "profile_form": profile_form,
        "password_form": password_form,
    })


@login_required
def delete_account(request):
    if request.method == "POST":
        user = request.user
        logout(request)
        user.delete()
        messages.info(request, "Your account and all its data were deleted.")
        return redirect("home")
    return render(request, "accounts/delete_account.html")


def seller_profile(request, pk):
    seller = get_object_or_404(User, pk=pk, is_active=True)
    listings = Listing.objects.live().filter(seller=seller).select_related("item", "item__category")
    reviews = seller.reviews_received.select_related("reviewer", "order__listing__item")[:20]
    return render(request, "accounts/seller_profile.html", {
        "seller": seller,
        "listings": listings,
        "reviews": reviews,
    })
