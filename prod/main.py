from fastapi import Depends, FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from models import User
from schema import users, database
from security import AuthHandler, RequiresLoginException
from fastapi import FastAPI, File, UploadFile
from gradio_client import Client
import os
import shutil, aiofiles

app = FastAPI()
# load static files
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/media", StaticFiles(directory="media"), name="media")
# load templates
templates = Jinja2Templates(directory="templates")
auth_handler = AuthHandler()
temp_dir_local = os.path.join(os.path.dirname(__file__), 'media')
os.makedirs(temp_dir_local, exist_ok=True)

# redirection block
@app.exception_handler(RequiresLoginException)
async def exception_handler(request: Request, exc: RequiresLoginException) -> Response:
    ''' this handler allows me to route the login exception to the login page.'''
    return RedirectResponse(url='/login/')        


@app.middleware("http")
async def create_auth_header(
    request: Request,
    call_next,
):
    
    if "Authorization" not in request.cookies:
        request.headers.__dict__["_list"].append(())
    
    elif "Authorization" not in request.headers and "Authorization" in request.cookies:
        access_token = request.cookies["Authorization"]

        # Check if the Authorization cookie needs to be deleted
        if "AuthorizationToDelete" not in request.cookies:
            request.headers.__dict__["_list"].append(
                (
                    "authorization".encode(),
                     f"Bearer {access_token}".encode(),
                )
            )
    elif "Authorization" not in request.headers and "Authorization" not in request.cookies:
        request.headers.__dict__["_list"].append(
            (
                "authorization".encode(),
                 f"Bearer 12345".encode(),
            )
        )

    response = await call_next(request)

    # Check if the AuthorizationToDelete cookie was set
    if "AuthorizationToDelete" in request.cookies:
        response.delete_cookie(key="Authorization", path="/")

    return response

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html",
     {"request": request})
    
@app.get("/login/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("login.html",
     {"request": request})


@app.get("/register/", response_class=HTMLResponse)
async def registration(request: Request):
    return templates.TemplateResponse("register.html",
     {"request": request})


@app.post("/register/", response_class=HTMLResponse)
async def register(request: Request, email: str = Form(...), password: str = Form(...)):
    user = User(email = email,
        password= password)    
    query = users.insert().values(email = user.email,
        password= auth_handler.get_hash_password(user.password))
    result = await database.execute(query)
    # TODO verify success and handle errors
    response = templates.TemplateResponse("success.html", 
              {"request": request, "success_msg": "Registration Successful!",
              "path_route": '/', "path_msg": "Click here to login!"})
    return response
    

@app.post("/login/")
async def sign_in(request: Request, response: Response,
    email: str = Form(...), password: str = Form(...)):
    try:
        user = User(email = email,
            password= password)  
        if await auth_handler.authenticate_user(user.email, user.password):
            atoken = auth_handler.create_access_token(user.email)
            response = templates.TemplateResponse("success.html", 
              {"request": request, "USERNAME": user.email, "success_msg": "Welcome back! "})
            
            response.set_cookie(key="Authorization", value= f"{atoken}", httponly=True)
            return response
        else:
            return templates.TemplateResponse("error.html",
            {"request": request, 'detail': 'Incorrect Username or Password', 'status_code': 404 })
    
    except Exception as err:
        return templates.TemplateResponse("error.html",
            {"request": request, 'detail': 'Incorrect Username or Password', 'status_code': 401 })
        

@app.get("/upload/", response_class=HTMLResponse)
async def private(request: Request, email=Depends(auth_handler.auth_wrapper)):
    try:
        if "Authorization" in request.cookies:
            return templates.TemplateResponse("upload.html",
                {"request": request})
    except:
        raise RequiresLoginException() 
    
@app.post("/user/upload")
async def create_upload_file(request: Request,file: UploadFile = File(...)):
    # save file to server
    local_file_path = os.path.join(temp_dir_local, file.filename)
    async with aiofiles.open(local_file_path, "wb") as new_file:
        # write the contents of the uploaded file to the new file
        content = await file.read()
        await new_file.write(content)
    
    #logic here to process the file
    client = Client("http://127.0.0.1:7862/")
    result = client.predict(local_file_path,api_name="/predict")
    
    shutil.copy(result[3], temp_dir_local)
    zip_location = "http://127.0.0.1:8002/media/" + result[3].split("/")[-1]
    
    return templates.TemplateResponse("upload.html",
                {"request": request,"summary":result[0], "transcript":result[1],"link":zip_location})

@app.post("/logout/", response_class= Response)
async def logout(request: Request, response: Response):
    if "Authorization" in request.cookies:   
        del request.cookies["Authorization"]     
        # Set a new cookie to be deleted in the middleware
        response.set_cookie(key="AuthorizationToDelete", path="/" )
    return RedirectResponse(url="/login/")