from allauth.account.adapter import DefaultAccountAdapter


class CustomAccountAdapter(DefaultAccountAdapter):
    def save_user(self, request, user, form, commit=True):
        # Call the parent class's save_user method
        user = super().save_user(request, user, form, commit=False)

        # Set is_organizer to True for new users
        user.is_organizer = True

        if commit:
            user.save()
        return user
