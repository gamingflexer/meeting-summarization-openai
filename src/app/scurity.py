from passlib.context import  CryptContext #pip install passlib
from fastapi.security import OAuth2PasswordBearer
from jose import jwt #https://pypi.org/project/python-jose/ = pip install python-jose
from fastapi import Depends,Request
from fastapi import HTTPException
 
from utils.models import UserModel
 
JWT_SECRET="cairocoders$§%§$Ednalan"
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES=3000
 
pwd_context=CryptContext(schemes=["bcrypt"],deprecated="auto") #pip install bcrypt
# save token to oauth2_scheme
oauth2_scheme=OAuth2PasswordBearer(tokenUrl="user/signin")
COOKIE_NAME="Authorization"
 
# create Token
def create_access_token(user):
    try:
        payload={
            "username":user.username,
            "email":user.email,
            "role":user.role.value,
            "active":user.is_active,

        }
        return  jwt.encode(payload,key=JWT_SECRET,algorithm=ALGORITHM)
    except Exception as ex:
        print(ex)
        raise ex
 
# create verify Token
def verify_token(token):
    try:
        return jwt.decode(token,key=JWT_SECRET)
    except Exception as ex:
        print(ex)
        raise ex
 
# password hash
def  get_password_hash(password):
    return pwd_context.hash(password)
 
# password verify
def verify_password(plain_password,hashed_password):
    return pwd_context.verify(plain_password,hashed_password)
 
def get_current_user_from_token(token:str=Depends(oauth2_scheme)):
    return verify_token(token)
 
def get_current_user_from_cookie(request:Request) -> UserModel:
    if token := request.cookies.get(COOKIE_NAME):
        return verify_token(token)