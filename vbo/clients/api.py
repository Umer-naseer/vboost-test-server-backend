import base64
import json
import logging
import operator
import os
import os.path
import uuid

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import (decorators, generics, pagination, permissions,
                            renderers, response, serializers, status, viewsets)
from rest_framework.authtoken.models import Token
from rest_framework.views import APIView

from campaigns.models import CampaignType, CampaignTypeImage
from generic.utils import user_ip
from packages.helpers import resize_image, rotate_jpeg

from .models import Campaign, Company, Contact, Event, Package, PackageImage


def customSuperUserMakeDir(path):
    splitted_path = path.split('/')
    for i in range(2, len(splitted_path)+1):
        try:
            os.system("sudo mkdir " + "/".join(splitted_path[:i]))
        except:
            continue


logger = logging.getLogger(__name__)


class SerializerMixin(object):
    def get_company(self):
        return self.context['view'].request.user.profile.company

    def validate_company(self, value):
        return self.get_company()


class ViewsetMixin(object):
    def get_queryset(self):
        return self.queryset.filter(
            company=self.request.user.profile.company
        ).exclude(company__isnull=True)


class CampaignTypeImageSerializer(serializers.ModelSerializer):
    # is_required = serializers.SerializerMethodField()

    def get_is_required(self, obj):
        return True

    class Meta:
        model = CampaignTypeImage
        fields = ['name', 'title']


class CampaignTypeSerializer(serializers.ModelSerializer):
    def to_representation(self, instance):
        repr = super(CampaignTypeSerializer, self).to_representation(instance)

        repr.update({
            'labels': [
                CampaignTypeImageSerializer(label).to_representation(label)
                for label in instance.images.all()
            ]
        })

        return repr

    class Meta:
        model = CampaignType
        fields = ['min_count', 'max_count', 'default_count']


class CampaignSerializer(SerializerMixin, serializers.ModelSerializer):
    color = serializers.SerializerMethodField(read_only=True)

    def get_color(self, obj):
        if obj.type_id:
            return obj.type.color

    def to_representation(self, instance):
        repr = super(CampaignSerializer, self).to_representation(instance)

        if instance.type_id:
            type = instance.type
            repr.update({
                'images': CampaignTypeSerializer(instance=type)
                .to_representation(instance=type)
            })

        return repr

    class Meta:
        model = Campaign
        fields = ['id', 'company', 'name', 'key', 'logo', 'details', 'color']


class CompanySerializer(SerializerMixin, serializers.ModelSerializer):
    logo = serializers.SerializerMethodField()

    def get_logo(self, obj):
        if obj.mobile_logo:
            return obj.mobile_logo.url

        elif obj.logo:
            return obj.logo.url

    class Meta:
        model = Company
        fields = ['id', 'key', 'name', 'logo', 'status', 'terms']


class SinglePackageImageSerializer(serializers.ModelSerializer):
    image = serializers.CharField()

    def create(self, validated_data):
        # self.is_valid(raise_exception=True)

        image = PackageImage.objects.create(
            name=self.validated_data['image']['name'],
            image=self.validated_data['image']['image'],
            package_id=int(self.validated_data['package'].id)
        )
        image.save()

        return image

    def validate_image(self, value):
        image = value

        if not image:
            raise serializers.ValidationError('Images are required.')

        name = self.context['request'].DATA['name']

        uid = uuid.uuid4().hex
        directory = 'images/{}/{}'.format(
            uid[:2],
            uid[2:4],
            uid
        )

        absolute_directory = os.path.join(
            settings.MEDIA_ROOT,
            directory
        )

        filename = '{uid}.jpg'.format(
            uid=uid,
        )

        # Save
        if not os.path.isdir(absolute_directory):
            os.makedirs(absolute_directory)

        with open(os.path.join(absolute_directory, filename), 'wb+') as f:
            f.write(base64.b64decode(image))

        resize_image(os.path.join(absolute_directory, filename))

        image_dict = dict()
        image_dict['image'] = os.path.join(
            directory,
            filename
        )
        image_dict['name'] = name

        return image_dict

    def validate_package(self, value):
        if value.company_id != self.context['request'].user.profile.company_id:
            raise serializers.ValidationError(
                'Wrone package ID. The package is not yours.'
            )
        return value

    class Meta:
        model = PackageImage
        fields = ['name', 'image', 'package']


class PackageImageViewSet(viewsets.ModelViewSet):
    serializer_class = SinglePackageImageSerializer
    queryset = PackageImage.objects.all()


class PackageImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PackageImage
        fields = ['name', 'image']


class PackageSerializer(SerializerMixin, serializers.ModelSerializer):
    images = PackageImageSerializer(many=True)
    company = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all(),
        required=False,
        allow_null=True,
        default=None
    )
    campaign = serializers.PrimaryKeyRelatedField(
        queryset=Campaign.objects.all(),
        required=True
    )
    recipient_signature = serializers.CharField(
        required=False, allow_blank=True
    )

    def get_fields(self):
        # Logging

        fields = super(PackageSerializer, self).get_fields()

        fields['campaign'].queryset = Campaign.objects.filter(
            company=self.get_company()
        ).exclude(company__isnull=True)

        fields['contact'].queryset = Contact.objects.filter(
            company=self.get_company()
        ).exclude(company__isnull=True)

        return fields

    def validate_recipient_signature(self, value):
        if not value:
            return value

        uid = uuid.uuid4().hex
        directory = 'signatures/{}/{}'.format(
            uid[:2],
            uid[2:4],
            uid
        )

        absolute_directory = os.path.join(
            settings.MEDIA_ROOT,
            directory
        )

        filename = '{}.jpg'.format(uid)

        # Save
        if not os.path.isdir(absolute_directory):
            os.makedirs(absolute_directory)

        with open(os.path.join(absolute_directory, filename), 'wb+') as f:
            f.write(base64.b64decode(value))

        return os.path.join(
            directory,
            filename
        )

    def validate_images(self, _):
        images_raw = self.context['view'].request.POST.get('images', None)

        try:
            images = json.loads(images_raw) if images_raw else []
        except ValueError as ve:
            raise serializers.ValidationError(
                'Cannot parse images: {}'.format(ve)
            )

        if not images:
            # raise serializers.ValidationError('Images are required.')
            return []

        try:
            names = filter(bool, [image['name'] for image in images])
        except KeyError:
            raise serializers.ValidationError('Image name is required.')

        if len(names) > len(set(names)):
            raise serializers.ValidationError(
                'Image names must be unique within a package.'
            )

        # Now AD-HOC solution to fix the image ordering. Pray Vishnu!
        if all(image['name'].startswith('Photo') for image in images):
            images.sort(key=operator.itemgetter('name'))

        # Convert image encoded base64 data to actual images
        for image in images:
            image_data = image.pop('image')
            if not image_data:
                raise serializers.ValidationError(
                    'No image supplied as {}.'.format(image['name'])
                )

            uid = uuid.uuid4().hex
            directory = 'images/{}/{}'.format(
                uid[:2],
                uid[2:4],
                uid
            )

            absolute_directory = os.path.join(
                settings.MEDIA_ROOT,
                directory
            )

            filename = '{uid}.jpg'.format(
                uid=uid,
            )

            # Save
            if not os.path.isdir(absolute_directory):
                os.makedirs(absolute_directory)

            with open(os.path.join(absolute_directory, filename), 'wb+') as f:
                f.write(base64.b64decode(image_data))

            rotate_jpeg(os.path.join(absolute_directory, filename))
            resize_image(os.path.join(absolute_directory, filename))

            image['image'] = os.path.join(
                directory,
                filename
            )

            # Remove bogus keys, thanks Mobiloitte sending garbage
            for key in image.keys():
                if key not in ['image', 'name']:
                    del image[key]

        return images

    def validate(self, data):
        """Checking image count"""

        type = data['campaign'].type
        min_count, max_count = type.min_count, type.max_count

        count = len(data['images'])

        if not ((min_count <= count <= max_count) or count == 0):
            raise serializers.ValidationError(
                'From {} to {} images permitted. '
                'Or it can be no images'.format(min_count, max_count)
            )

        return data

    def create(self, validated_data):
        images = validated_data.pop('images')

        validated_data.update({
            'company': self.get_company()
        })

        package = Package.objects.create(
            status='preparation',
            created_time=timezone.now(),
            user_agent=self.context['view'].request.META.get(
                'HTTP_USER_AGENT', 'Vboost'
            ),
            **validated_data
        )

        _ = [
            PackageImage.objects.create(
                package=package,
                inline_ordering_position=(i + 1),
                **image
            ) for i, image in enumerate(images)
        ]

        if images:
            package.status = 'pending'

        package.save()

        return package

    class Meta:
        model = Package
        fields = [
            'id', 'company', 'campaign', 'contact',
            'recipient_name', 'recipient_email', 'recipient_phone',
            'recipient_permission', 'recipient_signature',
            'images'
        ]


class ContactSerializer(SerializerMixin, serializers.ModelSerializer):
    company = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all(), required=False,
        allow_null=True, default=None
    )

    class Meta:
        model = Contact
        validators = []


class ContactViewSet(ViewsetMixin, viewsets.ModelViewSet):
    serializer_class = ContactSerializer
    permission_classes = [permissions.DjangoModelPermissions]
    queryset = Contact.objects.filter(
        is_active=True
    ).order_by('company', 'name')

    def get_queryset(self):
        queryset = super(ContactViewSet, self).get_queryset()

        if self.request.user.profile.company.filter_contacts:
            return queryset.filter(type='staff')
        else:
            return queryset

    @decorators.detail_route(
        renderer_classes=[renderers.JSONRenderer], methods=['POST']
    )
    def deactivate(self, request, *args, **kwargs):
        """Deactivate a contact."""
        instance = self.get_object()
        instance.is_active = False
        instance.save()

        serializer = self.get_serializer(instance)
        return response.Response(serializer.data)

    @decorators.detail_route(
        renderer_classes=[renderers.JSONRenderer], methods=['POST']
    )
    def activate(self, request, *args, **kwargs):
        """Activate a hidden contact."""
        lookup_url_kwarg = self.lookup_url_kwarg or self.lookup_field

        filter_kwargs = {self.lookup_field: self.kwargs[lookup_url_kwarg]}
        obj = generics.get_object_or_404(Contact.objects.filter(
            company=self.request.user.profile.company
        ), **filter_kwargs)

        # May raise a permission denied
        self.check_object_permissions(self.request, obj)

        serializer = self.get_serializer(obj)

        obj.is_active = True
        obj.save()

        serializer = self.get_serializer(obj)
        return response.Response(serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Try to find out a conflincting deactivated instance
        instance = Contact.objects.filter(
            name=serializer._validated_data['name'],
            company=serializer._validated_data['company']
        ).first()

        if instance:
            data = request.data.copy()
            data.update({'is_active': True})
            partial = True

            serializer = self.get_serializer(
                instance, data=data, partial=partial
            )
            serializer.is_valid(raise_exception=True)

            self.perform_update(serializer)
            return response.Response(serializer.data)

            # The following code is cool
            raise serializers.ValidationError({
                'non_field_errors': [
                    'This contact already exists in the database.'
                    + (
                        ' Do you want to reactivate this contact?'
                        if not instance.is_active else ''
                    )
                ],
                'id': instance.id,
                'is_active': instance.is_active,
            })

        else:
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            return response.Response(
                serializer.data,
                status=status.HTTP_201_CREATED,
                headers=headers
            )


class Pagination(pagination.PageNumberPagination):
    page_size = 10


class PackageCompleteView(generics.UpdateAPIView):

    def patch(self, request, *args, **kwargs):
        package_id = kwargs['pk']
        data = {
            'id': package_id,
            'result': 'Fail',
        }
        package = Package.objects.filter(id=package_id).first()

        if package and package.company_id != request.user.profile.company_id:
            data['result'] = 'Wrone package ID. The package is not yours.'
        else:
            package.status = 'pending'
            package.save()
            data['result'] = 'Success'

        return response.Response(data)


class PackageViewSet(ViewsetMixin, viewsets.ModelViewSet):
    serializer_class = PackageSerializer
    queryset = Package.objects.all()
    pagination_class = Pagination

    def create(self, request, *args, **kwargs):
        logger.info(
            'Mobile app package creation request initiated',
            extra={
                'request': request,
                'time': timezone.now(),
            }
        )

        response = super(PackageViewSet, self).create(request, *args, **kwargs)

        logger.info(
            'Mobile app package creation request completing',
            extra={
                'request': request,
                'time:': timezone.now(),
            }
        )
        return response


class CampaignViewSet(ViewsetMixin, viewsets.ModelViewSet):
    serializer_class = CampaignSerializer
    permission_classes = [permissions.DjangoModelPermissions]
    queryset = Campaign.objects.filter(
        is_active=True,
        type__isnull=False,
    ).order_by('type__order')


class CompanyView(generics.RetrieveAPIView):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer
    permission_classes = [permissions.DjangoModelPermissions]

    def check_object_permissions(self, request, obj):
        if not obj:
            self.permission_denied(request)

    def get_object(self):
        obj = self.request.user.profile.company

        self.check_object_permissions(self.request, obj)

        return obj


def help_view(request):
    from templates.models import Template
    template = Template.objects.filter(type='help').first()

    return HttpResponse(json.dumps({
        'help_text': template.render()
    }), content_type='application/json')


class EventSerializer(serializers.ModelSerializer):
    def validate(self, data):
        request = self.context['view'].request

        if data.get('type') == 'video':
            data['description'] = str(timezone.timedelta(
                seconds=data.get('duration', 0)
            ))

        # user information
        data.update({
            'ip': user_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', None)
        })

        return super(EventSerializer, self).validate(data)

    class Meta:
        model = Event
        fields = ['package', 'ip', 'id', 'user_agent', 'type', 'description',
                  'duration', 'service']


class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    permission_classes = []

    def list(self, request, *args, **kwargs):
        return response.Response([])

    def retrieve(self, request, *args, **kwargs):
        return response.Response({})


class UserDeactivateSerializer(serializers.ModelSerializer):

    class Meta:
        model = User
        fields =  ['id', 'is_active']

class UserDeactivateView(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserDeactivateSerializer

    def create(self, request, *args, **kwargs):
        try:
            user_id = request.data.get('id', None)
            is_active = request.data.get('is_active', None)
            user_data = User.objects.filter(id=user_id)

            if user_data.exists() and user_id:
                User.objects.filter(id=user_id).update(is_active=is_active)
                return response.Response({"is_active": is_active})
            return response.Response({"error": f"Please pass correct {user_id} -- {is_active}."})
        except Exception as e:
            return response.Response({"error": f"Please pass correct -- {user_id} -- {is_active}."})


class CustomLoginAPIView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, format=None):
        # Retrieve the login credentials from the request data
        username = request.data.get('username')
        password = request.data.get('password')
        
        # Perform the authentication
        user = authenticate(username=username, password=password)

        try:
            if user is None:
                return response.Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

            # Check the 'is_active' flag of the user
            is_active = user.is_active

            # Generate the auth token using Djoser
            # token = djoser_views.TokenCreateView.as_view()(request._request).data.get('auth_token')
            token, _ = Token.objects.get_or_create(user=user)

            # Create the response data
            response_data = {
                'auth_token': token.key,
                'is_active': is_active,
            }

            return response.Response(response_data, status=status.HTTP_200_OK)
        except Exception as ex:
            return response.Response({'error': f'Invalid {username} -- {password} -- {user.username} -- {user.is_active}'}, status=status.HTTP_401_UNAUTHORIZED)
