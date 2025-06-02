import os
from passlib.context import CryptContext

# Secret key for JWT. GENERATE A STRONG, RANDOM ONE!
# You can generate one with: python -c "import secrets; print(secrets.token_hex(32))"
# Store this in an environment variable for production!
import secrets; print(secrets.token_hex(32))
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "b8cbfededb9eaf54d82858bc4f5e9103ba83d0598fecc4fe0db3115a01fc4510")
ALGORITHM = "HS256" # Algorithm used for JWT signing

# Admin User Credentials (FOR DEMO/DEVELOPMENT ONLY)
# In a real application, these would come from a database.
# HASH YOUR PASSWORD! Use `pwd_context.hash("your_admin_password")` to generate.
# Example: print(pwd_context.hash("supersecurepassword"))
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
# This is a bcrypt hash of "password123". REPLACE WITH YOUR OWN HASHED PASSWORD.
# Use `from passlib.context import CryptContext; pwd_context = CryptContext(schemes=["bcrypt"]); print(pwd_context.hash("YOUR_NEW_PASSWORD"))`
# to generate your own hash.
ADMIN_HASHED_PASSWORD = os.getenv("ADMIN_HASHED_PASSWORD", "$2b$12$W491icrFGrOIzh46bhcCYufIuGEQchACzckbfcBC0DfvQPzgpCG4y") 
# The example hash is for "password123". Generate a new one for a real password.

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Token expiration time (in minutes)
ACCESS_TOKEN_EXPIRE_MINUTES = 30