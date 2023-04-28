from django.db.models.signals import m2m_changed, post_delete
from django.core.mail import EmailMultiAlternatives
from django.dispatch import receiver # импортируем нужный декоратор
from .models import PostCategory
from django.template.loader import render_to_string  # импортируем функцию, которая срендерит наш html в текст
from django.conf import settings


def send_notifications(preview, pk, name, subscribers):
    html_context = render_to_string(
        'news_creates_email.html',
        {
            'text': preview, # Краткий текст статьи
            'Link': f'{settings.SITE_URL}/news/{pk}',# ссылка на статью
        }
    )

    msg = EmailMultiAlternatives(
        subject=name,
        body='',
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=subscribers,
    )

    msg.attach_alternative(html_context, 'text/html')
    msg.send()

# в декоратор передаётся первым аргументом сигнал, на который будет реагировать эта функция, и в отправители надо передать также модель
@receiver(m2m_changed, sender=PostCategory)
# создаём функцию-обработчик с параметрами под регистрацию сигнала
def notify_about_new_post(sender, instance, **kwargs):
    # в зависимости от того, есть ли такой объект уже в базе данных или нет, тема письма будет разная
    if kwargs['action'] == 'news_add': # сигнал срабатывает только тогда когда статья создалась
         categories = instance.category.all()
         subscribers: list[str] = [] # создали список почты пользователей
         for category in categories:
            subscribers += category.subscribers.all()

         subscribers = [s.email for s in subscribers]

         send_notifications(instance.preview(), instance.pk, instance.name, instance.subscribers)


