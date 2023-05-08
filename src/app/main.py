#loginregister/main.py
from fastapi import FastAPI, Request, APIRouter,Depends,Form,HTTPException,Response
from starlette.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from utils.connection import Base,engine, sess_db
from sqlalchemy.orm import Session
from scurity import get_password_hash,verify_password, create_access_token, verify_token, COOKIE_NAME
from starlette.responses  import RedirectResponse
 
# Repository
from repositoryuser import UserRepository, SendEmailVerify
 
# Model
from utils.models import UserModel
 
templates = Jinja2Templates(directory="templates")
 
app = FastAPI()
app.mount("/static",StaticFiles(directory="static",html=True),name="static")
 
#db engin
Base.metadata.create_all(bind=engine)
 
@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
 
@app.get("/user/signup")
def signup(req: Request):
    return templates.TemplateResponse("signup.html", {"request": req})
 
@app.post("/signupuser")
def signup_user(db:Session=Depends(sess_db),username : str = Form(),email:str=Form(),password:str=Form()):
    userRepository=UserRepository(db)
    if userRepository.get_user_by_username(username):
        return "username is not valid"
 
    signup=UserModel(email=email,username=username,password=get_password_hash(password))
    success=userRepository.create_user(signup)
    token=create_access_token(signup)
    SendEmailVerify.sendVerify(token)
    if success:
        return "create  user successfully"
    else:
        raise HTTPException(
            status_code=401, detail="Credentials not correct"
        )
 
@app.get("/user/signin")
def login(req: Request):
    return templates.TemplateResponse("/signin.html", {"request": req})
 
@app.post("/signinuser")
def signin_user(response:Response,db:Session=Depends(sess_db),username : str = Form(),password:str=Form()):
    userRepository = UserRepository(db)
    db_user = userRepository.get_user_by_username(username)
    if not db_user:
        return "username or password is not valid"
 
    if verify_password(password,db_user.password):
        token=create_access_token(db_user)
        response.set_cookie(
            key=COOKIE_NAME,
            value=token,
            httponly=True,
            expires=1800
        )
        return {COOKIE_NAME:token,"token_type":"cairocoders"}
 
@app.get('/user/verify/{token}')
def verify_user(token,db:Session=Depends(sess_db)):
    userRepository=UserRepository(db)
    payload=verify_token(token)
    username=payload.get("username")
    db_user=userRepository.get_user_by_username(username)
 
    if not username:
        raise  HTTPException(
            status_code=401, detail="Credentials not correct"
        )
    if db_user.is_active==True:
        return "your account  has been allreay activeed"
 
    db_user.is_active=True
    db.commit()
    return RedirectResponse(url="/user/signin")
