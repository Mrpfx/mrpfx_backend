"""
Authentication service with WordPress-compatible password hashing.
"""
from datetime import datetime, timezone
from typing import Optional, Tuple
from fastapi import HTTPException, status, BackgroundTasks
from sqlmodel.ext.asyncio.session import AsyncSession

from app.model.user import User
from app.repo.user import UserRepository
from app.repo.wordpress.user import WPUserRepository
from app.repo.wordpress.options import WPOptionRepository
from app.schema.auth import SignupRequest, LoginRequest, TokenResponse
from app.schema.user import UserCreate
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_verification_code,
    generate_reset_token,
)
from app.core.config import settings
from app.service.email import send_verification_email, send_password_reset_email


class AuthService:
    """Service for handling authentication operations."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.user_repo = UserRepository(session)
        self.wp_user_repo = WPUserRepository(session)
        self.option_repo = WPOptionRepository(session)

    async def signup(self, request: SignupRequest, background_tasks: BackgroundTasks) -> Tuple[User, str]:
        """
        Register a new user.

        Args:
            request: Signup request with email, password, username
            background_tasks: Task queue for sending emails

        Returns:
            Tuple of (created user, verification code)

        Raises:
            HTTPException: If email or username already exists
        """
        # Check if email already exists
        if await self.user_repo.exists_by_email(request.email):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already registered"
            )

        # Check if username already exists
        if await self.user_repo.exists_by_login(request.username):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username already taken"
            )

        # Generate verification code
        verification_code = generate_verification_code()

        # Hash password using bcrypt (WordPress 6.8+ compatible)
        hashed_password = hash_password(request.password)

        # Create user
        user_data = UserCreate(
            user_login=request.username,
            user_pass=hashed_password,
            user_email=request.email,
            user_nicename=request.username.lower().replace(" ", "-"),
            user_url="",
            user_activation_key=verification_code,
            user_status=0,  # Unverified
            display_name=request.display_name or request.username,
        )

        user = await self.user_repo.create(user_data)

        # Send verification email via background task
        background_tasks.add_task(
            send_verification_email,
            email=request.email,
            code=verification_code,
            username=user.display_name or user.user_login
        )

        # Notify admin of new user via background task
        from app.core.config import settings
        from app.service.email import send_admin_new_user_email_notification
        if settings.ADMIN_EMAIL:
            background_tasks.add_task(
                send_admin_new_user_email_notification,
                admin_email=settings.ADMIN_EMAIL,
                new_username=user.user_login,
                new_user_email=user.user_email
            )

        return user, verification_code

    async def login(self, request: LoginRequest) -> TokenResponse:
        """
        Authenticate user and return tokens.

        Args:
            request: Login request with email/username and password

        Returns:
            TokenResponse with access and refresh tokens

        Raises:
            HTTPException: If credentials are invalid or user is unverified
        """
        user = await self.user_repo.get_by_email_or_login(request.login)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )

        if not verify_password(request.password, user.user_pass):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )

        # Check for forced password reset
        force_reset_date_str = await self.option_repo.get_option("force_password_reset_date")
        if force_reset_date_str:
            force_reset_date = int(force_reset_date_str)
            last_reset_str = await self.wp_user_repo.get_last_password_reset(user.ID)
            # Compare with user_registered as well
            from datetime import datetime
            try:
                # user_registered might be str "YYYY-MM-DD HH:MM:SS" or datetime
                reg_dt = user.user_registered if isinstance(user.user_registered, datetime) else datetime.strptime(user.user_registered, "%Y-%m-%d %H:%M:%S")
                reg_ts = int(reg_dt.timestamp())
            except (ValueError, TypeError):
                reg_ts = 0

            last_reset_ts = int(last_reset_str) if last_reset_str else 0

            # Use the most recent of the two
            effective_reset_ts = max(last_reset_ts, reg_ts)
            if effective_reset_ts < force_reset_date:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="PASSWORD_RESET_REQUIRED"
                )

        token_data = {"sub": str(user.ID), "email": user.user_email}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

    async def admin_login(self, request: LoginRequest) -> TokenResponse:
        """
        Authenticate admin user and return tokens.

        Args:
            request: Login request with email/username and password

        Returns:
            TokenResponse with access and refresh tokens

        Raises:
            HTTPException: If credentials are invalid or user is not an admin (status != 1)
        """
        user = await self.user_repo.get_by_email_or_login(request.login)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )

        if not verify_password(request.password, user.user_pass):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )

        if user.user_status != 1:
             raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied. Admin privileges required."
            )

        # Check for forced password reset (Admins also follow this policy)
        force_reset_date_str = await self.option_repo.get_option("force_password_reset_date")
        if force_reset_date_str:
            force_reset_date = int(force_reset_date_str)
            last_reset_str = await self.wp_user_repo.get_last_password_reset(user.ID)
            # Compare with user_registered as well
            from datetime import datetime
            try:
                # user_registered might be str "YYYY-MM-DD HH:MM:SS" or datetime
                reg_dt = user.user_registered if isinstance(user.user_registered, datetime) else datetime.strptime(user.user_registered, "%Y-%m-%d %H:%M:%S")
                reg_ts = int(reg_dt.timestamp())
            except (ValueError, TypeError):
                reg_ts = 0

            last_reset_ts = int(last_reset_str) if last_reset_str else 0

            # Use the most recent of the two
            effective_reset_ts = max(last_reset_ts, reg_ts)

            if effective_reset_ts < force_reset_date:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="PASSWORD_RESET_REQUIRED"
                )

        token_data = {"sub": str(user.ID), "email": user.user_email, "role": "admin"}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

    async def verify_email(self, email: str, code: str, background_tasks: BackgroundTasks) -> User:
        """
        Verify user email with code.

        Args:
            email: User's email
            code: Verification code from email
            background_tasks: Task queue for welcome email

        Returns:
            Verified user

        Raises:
            HTTPException: If code is invalid or user not found
        """
        user = await self.user_repo.get_by_email(email)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        if user.user_status == 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already verified"
            )

        if user.user_activation_key != code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification code"
            )

        # Activate user
        await self.user_repo.set_status(user, 1)
        await self.user_repo.set_activation_key(user, "")

        # Send welcome email via background task
        from app.service.email import send_welcome_email
        background_tasks.add_task(
            send_welcome_email,
            email=user.user_email,
            username=user.display_name or user.user_login
        )

        return user

    async def resend_verification(self, email: str, background_tasks: BackgroundTasks) -> bool:
        """
        Resend verification email.

        Args:
            email: User's email
            background_tasks: Task queue for sending emails

        Returns:
            True if email sent

        Raises:
            HTTPException: If user not found or already verified
        """
        user = await self.user_repo.get_by_email(email)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        if user.user_status == 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already verified"
            )

        # Generate new code
        verification_code = generate_verification_code()
        await self.user_repo.set_activation_key(user, verification_code)

        # Send email
        # Send email via background task
        background_tasks.add_task(
            send_verification_email,
            email=email,
            code=verification_code,
            username=user.display_name or user.user_login
        )

        return True

    async def forgot_password(self, email: str, background_tasks: BackgroundTasks) -> bool:
        """
        Initiate password reset.

        Args:
            email: User's email
            background_tasks: Task queue for sending emails

        Returns:
            True (always returns True to prevent email enumeration)
        """
        user = await self.user_repo.get_by_email(email)

        if not user:
            # Don't reveal if email exists
            return True

        # Generate reset token
        reset_token = generate_reset_token()
        await self.user_repo.set_activation_key(user, reset_token)

        # Send email
        # Send email via background task
        background_tasks.add_task(
            send_password_reset_email,
            email=email,
            token=reset_token,
            username=user.display_name or user.user_login
        )

        return True

    async def reset_password(self, email: str, token: str, new_password: str) -> User:
        """
        Reset user password with token.

        Args:
            email: User's email
            token: Reset token from email
            new_password: New password to set

        Returns:
            Updated user

        Raises:
            HTTPException: If token is invalid or expired
        """
        user = await self.user_repo.get_by_email(email)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )

        if not user.user_activation_key or user.user_activation_key != token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token"
            )

        # Hash new password
        hashed_password = hash_password(new_password)
        await self.user_repo.update_password(user, hashed_password)
        await self.user_repo.set_activation_key(user, "")

        # Update last reset timestamp and user_registered (requested by user)
        from sqlmodel import update
        user_id = user.ID
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[DEBUG] Direct SQL Update: user {user_id} registered date to {now_str}")

        await self.session.execute(
            update(User).where(User.ID == user_id).values(user_registered=now_str)
        )
        await self.session.commit()

        await self.wp_user_repo.update_last_password_reset(user_id)

        return user

    async def refresh_token(self, refresh_token: str) -> TokenResponse:
        """
        Generate new access token from refresh token.

        Args:
            refresh_token: Valid refresh token

        Returns:
            New TokenResponse with fresh tokens

        Raises:
            HTTPException: If refresh token is invalid
        """
        payload = decode_token(refresh_token)

        if not payload or payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )

        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )

        # Verify user still exists
        user = await self.user_repo.get_by_id(int(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )

        # Create new tokens
        token_data = {"sub": str(user.ID), "email": user.user_email}
        access_token = create_access_token(token_data)
        new_refresh_token = create_refresh_token(token_data)

        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

    async def change_password(
        self,
        user: User,
        current_password: str,
        new_password: str
    ) -> User:
        """
        Change user password.

        Args:
            user: Current user
            current_password: Current password for verification
            new_password: New password to set

        Returns:
            Updated user

        Raises:
            HTTPException: If current password is wrong
        """
        if not verify_password(current_password, user.user_pass):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )

        hashed_password = hash_password(new_password)
        await self.user_repo.update_password(user, hashed_password)

        # Update last reset timestamp and user_registered
        from sqlmodel import update
        user_id = user.ID
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        await self.session.execute(
            update(User).where(User.ID == user_id).values(user_registered=now_str)
        )
        await self.session.commit()

        await self.wp_user_repo.update_last_password_reset(user_id)

        return user
