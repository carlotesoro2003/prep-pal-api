from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from routes import (
    websocket_routes, 
    notification_routes, 
    upload_routes, 
    auth_routes,
    question_routes, 
    answer_routes,
    interview_routes
)
import asyncio
from session_notifications import session_notification_worker
from contextlib import asynccontextmanager
from dotenv import load_dotenv


# Load environment variables
load_dotenv()

# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     # Start the notification worker
#     notification_task = asyncio.create_task(session_notification_worker())
#     yield
#     # Cancel the task on shutdown
#     notification_task.cancel()
#     try:
#         await notification_task
#     except asyncio.CancelledError:
#         pass


# Initialize FastAPI app
app = FastAPI()

# @app.on_event("startup")
# async def startup_event():
#     asyncio.create_task(session_notification_worker())

# CORS middleware - IMPORTANT: This must be configured correctly
app.add_middleware(    
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  
    allow_credentials=True,  
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(websocket_routes.router, prefix="/api")
app.include_router(notification_routes.router, prefix="/api")
app.include_router(upload_routes.router, prefix="/api")
app.include_router(auth_routes.router)
app.include_router(question_routes.router)
app.include_router(answer_routes.router)
app.include_router(interview_routes.router)


app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")



# Root endpoint
@app.get("/")
def read_root():
    return {"message": "PrepPal API is running!", "version": "1.0.0"}





