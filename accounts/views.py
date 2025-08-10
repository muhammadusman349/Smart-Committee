from django.shortcuts import render, redirect
from django.db.models import Sum
from django.contrib.auth.decorators import login_required
from .forms import (
    UserUpdateForm,
    ProfileUpdateForm
)
from .models import Profile
from committee.models import Committee, Membership, Contribution


# Simplified home function to redirect authenticated users and show basic stats for unauthenticated users
def home(request):
    if request.user.is_authenticated:
        if request.user.is_organizer:
            return redirect('committee:organizer_dashboard')
        else:
            return redirect('committee:member_dashboard')  # Fallback for members
    else:
        context = {
            'total_committees_all': Committee.objects.count(),
            'total_members_all': Membership.objects.count(),
            'total_contributions_all': Contribution.objects.filter(payment_status='PAID').aggregate(total=Sum('amount_paid'))['total'] or 0,
        }
        return render(request, 'home.html', context)


@login_required
def profile_view(request):
    # Get or create profile for the user
    profile, created = Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=request.user)
        profile_form = ProfileUpdateForm(
            request.POST, 
            request.FILES, 
            instance=profile
        )
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            return redirect('profile')
    else:
        user_form = UserUpdateForm(instance=request.user)
        profile_form = ProfileUpdateForm(instance=profile)

    return render(request, 'accounts/profile.html', {
        'user_form': user_form,
        'profile_form': profile_form
    })
