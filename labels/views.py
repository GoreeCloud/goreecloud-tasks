"""Authorization-aware label management."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .forms import LabelCreateForm
from .models import Label


@login_required
def label_list(request):
    """List accessible labels and create labels only in editable scopes."""
    if request.method == "POST":
        form = LabelCreateForm(request.POST, user=request.user)
        if form.is_valid():
            label = form.save(commit=False)
            label.owner = request.user
            label.save()
            messages.success(request, "Label created.")
            return redirect("labels:list")
    else:
        form = LabelCreateForm(user=request.user)

    labels = list(
        Label.objects.visible_to(request.user)
        .select_related("project", "owner")
        .order_by("project__name", "name", "id")
    )
    editable_ids = set(
        Label.objects.editable_by(request.user)
        .filter(pk__in=[label.pk for label in labels])
        .values_list("pk", flat=True)
    )
    for label in labels:
        label.user_can_edit = label.pk in editable_ids

    return render(
        request,
        "labels/label_list.html",
        {
            "labels": labels,
            "form": form,
            "active_view": "labels",
        },
    )


@login_required
@require_POST
def label_delete(request, pk):
    """Delete an unused label only when the current user may manage its scope."""
    label = get_object_or_404(Label.objects.editable_by(request.user), pk=pk)
    if label.tasks.exists():
        messages.error(
            request,
            "This label is still assigned to tasks. Remove it from those tasks before deleting it.",
        )
        return redirect("labels:list")

    label.delete()
    messages.success(request, "Label deleted.")
    return redirect("labels:list")
