# (venv) ~/django-projects/Mac $ python manage.py makemigrations
# (venv) ~/django-projects/Mac $ python manage.py migrate
# (venv) ~/django-projects/Mac $ python manage.py shell


from django.db import models
from django.contrib.auth.models import User
from django.urls import reverse
from datetime import datetime
from django.contrib.auth.forms import UserCreationForm
from django import forms
from allauth.account.forms import SignupForm
from django.contrib.auth.models import Group
from django.template.loader import render_to_string  # импортируем функцию, которая срендерит наш html в текст
from django.core.mail import send_mail
from django.db.models.signals import post_save
from django.utils.html import strip_tags
from django.contrib.auth import authenticate, login
from django.contrib.sites.shortcuts import get_current_site
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.conf import settings

from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm


class CommonSignupForm(SignupForm):

    def save(self, request):
        user = super(CommonSignupForm, self).save(request)
        common_group = Group.objects.get(name='common')
        common_group.user_set.add(user)
        return user

class BaseRegisterForm(UserCreationForm):
    email = forms.EmailField(label = "Email")
    first_name = forms.CharField(label = "Имя")
    last_name = forms.CharField(label = "Фамилия")

    class Meta:
        model = User
        fields = ("username",
                  "first_name",
                  "last_name",
                  "email",
                  "password1",
                  "password2",
        )

# Модель, содержащая объекты всех авторов.
# cвязь «один к одному» с встроенной моделью пользователей User;
class Author(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    rating = models.IntegerField(default=0)
    username = models.CharField(max_length=255, unique=True, null=True, blank=True)
    #рейтинг пользователя. Ниже будет дано описание того, как этот рейтинг можно посчитать.

    def __str__(self):
        return self.username

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = self.user.username
        super(Author, self).save(*args, **kwargs)

    def update_rating(self):
        post_rating = sum(post.rating for post in self.user.news.all())
        comment_rating = sum(self.user.comments.all().values_list('rating', flat=True))
        self.rating = post_rating * 3 + comment_rating
        self.save()

# Удаление дубликатов
duplicates = Author.objects.values('username').annotate(
    max_id=models.Max('id'), count_id=models.Count('id')
).filter(count_id__gt=1)

for duplicate in duplicates:
    Author.objects.filter(username=duplicate['username']).exclude(
        id=duplicate['max_id']
    ).delete()

# Категории новостей/статей — темы, которые они отражают (спорт, политика, образование и т. д.).
# Имеет единственное поле: название категории. Поле должно быть уникальным
# (в определении поля необходимо написать параметр unique = True).
class Category(models.Model):
    name = models.CharField(max_length=255, unique=True)
    subscribers = models.ManyToManyField(User, related_name='categories')

    def __str__(self):
       return self.name

# Новости
class News(models.Model):
    # POST_TYPES = (
    #     ('article', 'Article'),
    #     ('news', 'News')
    # )
    name = models.CharField(max_length=255, unique=True,) # названия новостей не должны повторяться
    description = models.TextField()
    category = models.ManyToManyField(Category, through='PostCategory')
    #post_type = models.CharField(max_length=7, choices=POST_TYPES)
    published_date = models.DateTimeField(default=datetime.now)  # предоставляем значение по умолчанию
    author = models.ForeignKey('Author', on_delete=models.CASCADE, related_name='news')
    rating = models.IntegerField(default=0)

    def update_rating(self):
        self.rating = self.likes.all().count() - self.dislikes.all().count()
        self.save()
        self.author.update_rating(self)

    def preview(self):
        if len(self.description) > 127:
            return self.description[:124] + '...'
        else:
            return self.description

    def __str__(self):
        return f'{self.name.name()}: {self.description[:20]}: {self.published_date}: {self.author} '

    def get_absolute_url(self):
        return reverse('news_detail', args=[str(self.id)])

    # send_notification, который отправляет электронное письмо подписчикам при добавлении новой статьи:
    def send_notification(self):
        subscribers = self.category.subscribers.all()
        for subscriber in subscribers:
            subject = self.name
            html_message = render_to_string('welcome_email.html', {
                'header': f'<h1>{self.name}</h1>',
                'preview': self.preview(),
                'username': subscriber.username,
            })
            plain_message = strip_tags(html_message)
            from_email = 'poc47a.t@yandex.ru'
            to_email = subscriber.email
            send_mail(subject, plain_message, from_email, [to_email], html_message=html_message)

class PostCategory(models.Model):
    post = models.ForeignKey(News, on_delete=models.CASCADE, related_name='post_categories')
    category = models.ForeignKey(Category, on_delete=models.CASCADE)



class Comment(models.Model):
    post = models.ForeignKey(News, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    rating = models.IntegerField(default=0)

    def update_rating(self):
        self.rating = self.likes.all().count() - self.dislikes.all().count()
        self.save()
        self.post.update_rating()
        self.user.author.update_rating()

    def like(self):
        self.rating += 1
        self.save()
        self.update_rating()

    def dislike(self):
        self.rating -= 1
        self.save()
        self.update_rating()

    def __str__(self):
        return self.text

class Like(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    post = models.ForeignKey(News, on_delete=models.CASCADE, related_name='likes')

class Dislike(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    post = models.ForeignKey(News, on_delete=models.CASCADE, related_name='dislikes')
