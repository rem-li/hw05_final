from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from django.core.cache import cache

from ..models import Group, Post

User = get_user_model()


class PostModelTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='auth')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание',
        )
        cls.post = Post.objects.create(
            author=cls.user,
            text='Тестовый пост',
        )

    def setUp(self):
        cache.clear()
        self.guest_client = Client()
        self.user = User.objects.create_user(username='HasNoName')
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)
        self.post_author = Client()
        self.post_author.force_login(PostModelTest.user)

    def test_url_exists_at_desired_location(self):
        """Страница доступна любому пользователю."""
        url_adress = {
            '/': 200,
            f'/group/{self.group.slug}/': 200,
            '/profile/auth/': 200,
            f'/posts/{self.post.id}/': 200,
            '/about/author/': 200,
            '/about/tech/': 200,
        }
        for address, code in url_adress.items():
            with self.subTest(address=address):
                response = self.guest_client.get(address)
                self.assertEqual(response.status_code, code)

    def test_create_url_exists_at_desired_location(self):
        """Страница по адресу /create/ доступна зарегистрированному
        пользователю.
        """
        response_names = [
            self.guest_client.get('/create/', follow=True),
            self.guest_client.post('/create/', follow=True),
        ]
        for response_name in response_names:
            with self.subTest(response_name=response_name):
                self.assertEqual(response_name.status_code, 200)

    def test_create_url_redirect_anonymous_on_post_detail(self):
        """Страница по адресу /create/ перенаправит анонимного
        пользователя на страницу логина.
        """
        response_names = [
            self.guest_client.get('/create/', follow=True),
            self.guest_client.post('/create/', follow=True),
        ]
        for response_name in response_names:
            with self.subTest(response_name=response_name):
                self.assertRedirects(
                    response_name, ('/auth/login/?next=/create/'))

    def test_edit_url_exists_for_post_author(self):
        """Страница по адресу /posts/{self.post.id}/edit/ доступна
        автору поста.
        """
        response_names = [
            self.post_author.get(f'/posts/{self.post.id}/edit/'),
            self.post_author.post(f'/posts/{self.post.id}/edit/')
        ]
        for response_name in response_names:
            with self.subTest(response_name=response_name):
                self.assertEqual(response_name.status_code, 200)

    def test_edit_url_redirect_nonauthor_on_post_id(self):
        """Страница по адресу /posts/{self.post.id}/edit/ перенаправит
        не-автора на страницу поста.
        """
        response_names = [
            self.authorized_client.get(f'/posts/{self.post.id}/edit/',
                                       follow=True),
            self.authorized_client.post(f'/posts/{self.post.id}/edit/',
                                        follow=True)
        ]
        for response_name in response_names:
            with self.subTest(response_name=response_name):
                self.assertRedirects(response_name,
                                     (f'/posts/{self.post.id}/'))

    def test_unexisting_page(self):
        """Страница по несуществующему адресу покажет ошибку."""
        response = self.authorized_client.get('/unexisting-page/')
        self.assertEqual(response.status_code, 404)

    def test_urls_uses_correct_template(self):
        """URL-адрес использует соответствующий шаблон."""
        templates_url_names = {
            '/': 'posts/index.html',
            '/group/test-slug/': 'posts/group_list.html',
            '/profile/auth/': 'posts/profile.html',
            f'/posts/{self.post.id}/': 'posts/post_detail.html',
            '/create/': 'posts/create_post.html',
            f'/posts/{self.post.id}/edit/': 'posts/create_post.html',
            '/about/author/': 'about/author.html',
            '/about/tech/': 'about/tech.html',
            '/nonexisting-page': 'core/404.html',
        }
        for address, template in templates_url_names.items():
            with self.subTest(address=address):
                response = self.post_author.get(address)
                self.assertTemplateUsed(response, template)
