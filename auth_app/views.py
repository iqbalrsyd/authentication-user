from django.shortcuts import render
from rest_framework.generic import GenericAPIView # type: ignore
from .serializers import UserRegisterSerializer
from rest_framework.response import Response # type: ignore
from rest_framework import status # type: ignore
from .utils import send_code_to_user 
# Create your views here.

class RegisterUserView(GenericAPIView):
    serializer_class = UserRegisterSerializer
    
    def post(self, request):
        user_data = request.data
        serializer = self.serializer_class(data=user_data)
        if serializer.is_valid(raise_exception=True):
            serializer.save()
            user = serializer.data
            send_code_to_user(user['email'], user['code'])
            #send email
            return Response({
                'data': user,
                'message': f'hi {user.first_name}, your account has been created successfully'
            }, status = status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)