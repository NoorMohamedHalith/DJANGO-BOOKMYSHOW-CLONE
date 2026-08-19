from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, HttpResponseBadRequest
from django.contrib import messages
from movies.models import Movie
from .models import Review, ReviewReport
from .services import ReviewEligibilityService


@login_required(login_url='/login/')
def add_review(request, movie_id):
    movie = get_object_or_404(Movie, id=movie_id)
    if request.method == 'POST':
        # Backend eligibility re-validation
        valid_booking = ReviewEligibilityService.get_eligible_booking(request.user, movie)
        if not valid_booking:
            messages.error(request, "You are not eligible to review this movie. Only viewers with completed bookings can leave a review.")
            return redirect('theater_list', movie_id=movie.id)

        # Check if user already submitted a review
        existing_review = Review.objects.filter(movie=movie, user=request.user).first()
        if existing_review:
            messages.warning(request, "You have already reviewed this movie. You can edit your existing review.")
            return redirect('theater_list', movie_id=movie.id)

        try:
            rating = int(request.POST.get('rating', 0))
            if rating < 1 or rating > 5:
                raise ValueError("Rating must be between 1 and 5.")
        except (ValueError, TypeError):
            messages.error(request, "Invalid rating value.")
            return redirect('theater_list', movie_id=movie.id)

        review_text = request.POST.get('review_text', '').strip()
        if not review_text:
            messages.error(request, "Review text cannot be empty.")
            return redirect('theater_list', movie_id=movie.id)

        Review.objects.create(
            movie=movie,
            user=request.user,
            booking=valid_booking,
            rating=rating,
            review_text=review_text,
            is_verified=True
        )
        messages.success(request, "Your review has been submitted successfully!")
    return redirect('theater_list', movie_id=movie.id)


@login_required(login_url='/login/')
def edit_review(request, review_id):
    review = get_object_or_404(Review, id=review_id)
    
    # Ownership Security Check
    if review.user != request.user:
        return HttpResponseForbidden("You are not authorized to edit this review.")

    if request.method == 'POST':
        try:
            rating = int(request.POST.get('rating', 0))
            if rating < 1 or rating > 5:
                raise ValueError("Rating must be between 1 and 5.")
        except (ValueError, TypeError):
            messages.error(request, "Invalid rating value.")
            return redirect('theater_list', movie_id=review.movie.id)

        review_text = request.POST.get('review_text', '').strip()
        if not review_text:
            messages.error(request, "Review text cannot be empty.")
            return redirect('theater_list', movie_id=review.movie.id)

        review.rating = rating
        review.review_text = review_text
        review.save()
        messages.success(request, "Your review has been updated successfully!")

    return redirect('theater_list', movie_id=review.movie.id)


@login_required(login_url='/login/')
def report_review(request, review_id):
    review = get_object_or_404(Review, id=review_id)
    
    # User cannot report their own review
    if review.user == request.user:
        messages.error(request, "You cannot report your own review.")
        return redirect('theater_list', movie_id=review.movie.id)

    if request.method == 'POST':
        # Check for duplicate report
        existing_report = ReviewReport.objects.filter(review=review, reported_by=request.user).first()
        if existing_report:
            messages.warning(request, "You have already reported this review.")
            return redirect('theater_list', movie_id=review.movie.id)

        reason = request.POST.get('reason', '').strip()
        if not reason:
            reason = "Inappropriate content"

        ReviewReport.objects.create(
            review=review,
            reported_by=request.user,
            reason=reason,
            status='PENDING'
        )
        messages.success(request, "The review has been reported for admin review.")

    return redirect('theater_list', movie_id=review.movie.id)
