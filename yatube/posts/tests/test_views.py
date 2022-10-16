from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django import forms
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.cache import cache

from ..models import Group, Post, Follow

User = get_user_model()


class PostModelTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        small_gif = (
             b'\x47\x49\x46\x38\x39\x61\x02\x00'
             b'\x01\x00\x80\x00\x00\x00\x00\x00'
             b'\xFF\xFF\xFF\x21\xF9\x04\x00\x00'
             b'\x00\x00\x00\x2C\x00\x00\x00\x00'
             b'\x02\x00\x01\x00\x00\x02\x02\x0C'
             b'\x0A\x00\x3B'
        )
        uploaded = SimpleUploadedFile(
            name='small.gif',
            content=small_gif,
            content_type='image/gif'
        )
        cls.user = User.objects.create_user(username='auth')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание',
        )
        cls.post = Post.objects.create(
            author=cls.user,
            group=cls.group,
            text='Тестовый пост',
            image=uploaded
        )

    def setUp(self):
        cache.clear()
        self.guest_client = Client()
        self.user = User.objects.create_user(username='HasNoName')
        self.authorized_client = Client()
        self.authorized_client.force_login(self.user)
        self.post_author = Client()
        self.post_author.force_login(PostModelTest.user)

    def test_pages_uses_correct_template(self):
        """URL-адрес использует соответствующий шаблон."""
        templates_pages_names = {
            reverse('posts:index'): 'posts/index.html',
            reverse('posts:group_posts', kwargs={'slug': 'test-slug'}):
                'posts/group_list.html',
            reverse('posts:profile', kwargs={'username': 'HasNoName'}):
                'posts/profile.html',
            reverse('posts:post_detail', kwargs={'post_id': '1'}):
                'posts/post_detail.html',
            reverse('posts:post_edit', kwargs={'post_id': '1'}):
                'posts/create_post.html',
            reverse('posts:post_create'): 'posts/create_post.html',
            reverse('about:author'): 'about/author.html',
            reverse('about:tech'): 'about/tech.html',
        }
        for reverse_name, template in templates_pages_names.items():
            with self.subTest(reverse_name=reverse_name):
                response = self.post_author.get(reverse_name)
                self.assertTemplateUsed(response, template)

    def test_pages_show_correct_context(self):
        """Шаблоны index, group_posts и profile сформированы с
        правильным контекстом."""
        reverse_names = [
            reverse('posts:index'),
            reverse('posts:group_posts', kwargs={'slug': self.group.slug}),
            reverse('posts:profile',
                    kwargs={'username': PostModelTest.user.username}),
        ]
        for reverse_name in reverse_names:
            with self.subTest(reverse_name=reverse_name):
                response = self.authorized_client.get(reverse_name)
                first_object = response.context['page_obj'][0]
                self.assertEqual(first_object, self.post)

    def test_post_detail_pages_show_correct_context(self):
        """Шаблон post_detail сформирован с правильным контекстом."""
        response = (self.authorized_client.
                    get(reverse('posts:post_detail',
                                kwargs={'post_id': self.post.pk})))
        self.assertEqual(response.context.get('post_open'), self.post)

    def test_post_create_show_correct_context(self):
        """Шаблоны post_create и post_edit сформированы
        с правильным контекстом."""
        reverse_names = [
            reverse('posts:post_create'),
            reverse('posts:post_edit', kwargs={'post_id': self.post.pk}),
        ]
        for reverse_name in reverse_names:
            with self.subTest(reverse_name=reverse_name):
                response = self.post_author.get(reverse_name)
                form_fields = {
                    'text': forms.fields.CharField,
                    'group': forms.fields.ChoiceField,
                    'image': forms.fields.ImageField,
                }
                for value, expected in form_fields.items():
                    with self.subTest(value=value):
                        form_field = (response.context.get('form')
                                      .fields.get(value))
                        self.assertIsInstance(form_field, expected)

    def test_post_appears_on_index_profile_group_pages(self):
        """Новый пост появляется на страницах index, group_posts и profile"""
        reverse_names = [
            reverse('posts:index'),
            reverse('posts:group_posts', kwargs={'slug': self.group.slug}),
            reverse('posts:profile',
                    kwargs={'username': PostModelTest.user.username}),
        ]
        new_post = Post.objects.create(
            author=PostModelTest.user,
            group=self.group,
            text='Новый тестовый пост',
        )
        for reverse_name in reverse_names:
            with self.subTest(reverse_name=reverse_name):
                response = self.authorized_client.get(reverse_name)
                first_object = response.context['page_obj'][0]
                self.assertEqual(first_object, new_post)

    def test_deleted_post_stays_in_index_cashe(self):
        """Удаленный из базы данных пост остается в response.content"""
        self.test_post = Post.objects.create(
            author=self.user,
            group=self.group,
            text='Тестовый пост для кэша'
        )
        response_one = (
            self.authorized_client.get(reverse('posts:index')).content
        )
        self.test_post.delete()
        response_two = (
            self.authorized_client.get(reverse('posts:index')).content
        )
        self.assertEqual(response_one, response_two)
        cache.clear()
        response_three = (
            self.authorized_client.get(reverse('posts:index')).content
        )
        self.assertNotEqual(response_three, response_one)


class FollowModelTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.post_author = User.objects.create_user(username='author')
        cls.follower = User.objects.create_user(username='follow')
        cls.nonfollower = User.objects.create_user(username='nonfollow')

    def setUp(self):
        cache.clear()
        self.guest_client = Client()
        self.authorized_follower = Client()
        self.authorized_follower.force_login(self.follower)
        self.authorized_nonfollower = Client()
        self.authorized_nonfollower.force_login(self.nonfollower)

    def test_authorized_user_can_follow(self):
        """Зарегистрированный пользователь может подписаться"""
        reverse_name = reverse(
                               'posts:profile_follow',
                               kwargs={'username': self.post_author}
        )
        self.authorized_follower.get(reverse_name)
        self.assertTrue(
            Follow.objects.filter(
                user=self.follower,
                author=self.post_author,
            ).exists()
        )

    def test_authorized_user_can_unfollow(self):
        """Зарегистрированный пользователь может отписаться"""
        Follow.objects.create(author=self.post_author, user=self.follower)
        reverse_name = reverse(
                               'posts:profile_unfollow',
                               kwargs={'username': self.post_author}
        )
        self.authorized_follower.get(reverse_name)
        self.assertFalse(
            Follow.objects.filter(
                user=self.follower,
                author=self.post_author,
            ).exists()
        )

    def test_post_appears_on_follow_index(self):
        """Новый пост появляется у подписанных"""
        Follow.objects.create(author=self.post_author, user=self.follower)
        new_post = Post.objects.create(
            author=self.post_author,
            text='Новый тестовый пост',
        )
        response = self.authorized_follower.get(reverse('posts:follow_index'))
        first_object = response.context['page_obj'][0]
        self.assertEqual(first_object, new_post)

    def test_post_does_not_appears_on_follow_index(self):
        """Новый пост не появляется у не подписанных"""
        new_post = Post.objects.create(
            author=self.post_author,
            text='Новый тестовый пост',
        )
        response = self.authorized_nonfollower.get(reverse('posts:follow_index'))
        self.assertEqual(len(response.context['page_obj']), 0)


class PaginatorViewsTest(TestCase):
    PAGE_TEST_OFFSET = 2

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = User.objects.create_user(username='auth')
        cls.group = Group.objects.create(
            title='Тестовая группа',
            slug='test-slug',
            description='Тестовое описание',
        )
        for num in range(settings.POSTS_PER_PAGE
                         + PaginatorViewsTest.PAGE_TEST_OFFSET):
            Post.objects.create(
                author=cls.user,
                group=cls.group,
                text=f'Тестовый пост номер {num}',
            )

    def setUp(cls):
        cache.clear()

    def test_first_page_contains_POSTS_PER_PAGE_records(self):
        reverse_names = [
            reverse('posts:index'),
            reverse('posts:group_posts', kwargs={'slug': 'test-slug'}),
            reverse('posts:profile', kwargs={'username': 'auth'}),
        ]
        for reverse_name in reverse_names:
            with self.subTest(reverse_name=reverse_name):
                response = self.client.get(reverse_name)
                self.assertEqual(len(response.context['page_obj']),
                                 settings.POSTS_PER_PAGE)

    def test_second_page_contains_PAGE_TEST_OFFSET_records(self):
        reverse_names = [
            reverse('posts:index'),
            reverse('posts:group_posts', kwargs={'slug': 'test-slug'}),
            reverse('posts:profile', kwargs={'username': 'auth'}),
        ]
        for reverse_name in reverse_names:
            with self.subTest(reverse_name=reverse_name):
                response = self.client.get(reverse_name + '?page=2')
                self.assertEqual(len(response.context['page_obj']),
                                 PaginatorViewsTest.PAGE_TEST_OFFSET)
