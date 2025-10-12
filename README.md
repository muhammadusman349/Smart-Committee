# Smart-Committee System 🏛️

A comprehensive **Django-based Committee Management System** designed for seamless financial collaboration and committee administration. Built with modern web technologies, this system enables organizers to create committees, manage memberships, track contributions, and handle payouts efficiently.

![Django](https://img.shields.io/badge/Django-5.2-green.svg)
![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3.0-38B2AC.svg)
![Celery](https://img.shields.io/badge/Celery-5.5.3-orange.svg)
![PostgreSQL](https://img.shields.io/badge/Database-SQLite3-blue.svg)

## 🌟 Key Features

### **Core Functionality**
- **Multi-Role User System** - Organizers and Members with distinct permissions
- **Committee Creation & Management** - Flexible committee setup with customizable durations
- **Membership Management** - Join/leave committees with status tracking
- **Monthly Contributions** - Automated contribution tracking and verification
- **Payout Distribution** - Streamlined fund distribution to members
- **Real-time Dashboard** - Comprehensive analytics and status monitoring

### **Advanced Features**
- **📧 Email Invitation System** - Secure token-based member invitations
- **📊 Automated Report Generation** - Excel/PDF reports with Celery background processing
- **💬 Contact Management** - Admin contact system with reply functionality
- **🎨 Modern UI/UX** - Professional design with Tailwind CSS
- **📱 Responsive Design** - Optimized for all device sizes
- **🔄 Background Tasks** - Async processing with Celery and RabbitMQ

## 🚀 Quick Start

### **Prerequisites**
- Python 3.8 or higher
- RabbitMQ (for Celery background tasks)
- Git

### **Installation**

1. **Clone the repository**
   ```bash
   git clone https://github.com/your-username/Smart-Committee.git
   cd Smart-Committee
   ```

2. **Create and activate virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Configuration**
   ```bash
   cp .env.example .env
   # Edit .env file with your configuration
   ```

5. **Database Setup**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

6. **Create Superuser**
   ```bash
   python manage.py createsuperuser
   ```

7. **Start RabbitMQ Server**
   ```bash
   # On Linux/Mac
   sudo systemctl start rabbitmq-server

   # On Windows, download and install RabbitMQ
   ```

8. **Start Celery Worker**
   ```bash
   celery -A conf worker --loglevel=info
   ```

9. **Run Development Server**
   ```bash
   python manage.py runserver
   ```

10. **Access the application**
    - **Admin Panel**: `http://localhost:8000/admin/`
    - **Main Application**: `http://localhost:8000/`

## 🏗️ System Architecture

### **Models Overview**

#### **User Management**
- **Custom User Model** - Email-based authentication with profile support
- **Role-based Access** - Organizers vs Members with different permissions

#### **Committee System**
- **Committee Model** - Core committee with status, duration, and monthly amounts
- **Membership Model** - User-committee relationships with join/leave tracking
- **Contribution Model** - Monthly payments with verification and reporting
- **Payout Model** - Fund distribution with confirmation tracking

#### **Communication**
- **Invitation Model** - Token-based email invitations with expiration
- **Contact Model** - Admin contact management with reply system

### **Technology Stack**

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Backend** | Django 5.2 | Web framework |
| **Database** | SQLite3 | Primary data storage |
| **Frontend** | Tailwind CSS | Styling and UI components |
| **Forms** | Django Crispy Forms | Form rendering and validation |
| **Authentication** | Django Allauth | User authentication and social login |
| **Background Tasks** | Celery + RabbitMQ | Async processing |
| **Report Generation** | Pandas, ReportLab | Excel/PDF report creation |
| **Email** | Django SMTP | Email notifications |

## 📋 Features Breakdown

### **1. Committee Management**
- ✅ Create committees with custom duration and monthly contribution amounts
- ✅ Automatic committee completion based on end dates
- ✅ Status management (Active/Deactivated/Completed)
- ✅ Committee reactivation and deactivation controls

### **2. Member Management**
- ✅ Email-based user registration and authentication
- ✅ Role switching between Organizer and Member
- ✅ Profile management with avatars and personal information
- ✅ Membership status tracking (Active/Left/Removed)

### **3. Contribution System**
- ✅ Monthly contribution tracking with due dates
- ✅ Automatic late payment detection
- ✅ Organizer verification system
- ✅ Bulk contribution management
- ✅ Contribution status management (Paid/Pending/Late)

### **4. Payout Management**
- ✅ Fund distribution to committee members
- ✅ Payment method tracking (Cash/Transfer)
- ✅ Confirmation system for received payments
- ✅ Payout status tracking and reporting

### **5. Invitation System**
- ✅ Token-based email invitations with 7-day expiration
- ✅ Secure invitation acceptance flow
- ✅ Invitation status management (Pending/Accepted/Expired)
- ✅ Resend and revoke invitation capabilities

### **6. Report Generation**
- ✅ Automated Excel and PDF report generation
- ✅ Background processing with Celery
- ✅ Member-specific and organizer reports
- ✅ Date range filtering for custom reports
- ✅ Secure file download system

### **7. Contact System**
- ✅ Admin contact management interface
- ✅ Contact categorization (General/Support/Business/Newsletter)
- ✅ Admin reply system with email notifications
- ✅ Contact status tracking (New/Read/Replied)

## 🎨 User Interface

### **Modern Design Features**
- **Responsive Layout** - Works perfectly on desktop, tablet, and mobile
- **Professional Styling** - Modern gradient headers and card-based layouts
- **Interactive Elements** - Hover effects, animations, and smooth transitions
- **Status Indicators** - Color-coded status badges and progress indicators
- **Dark Mode Support** - Built-in dark mode toggle
- **Accessibility** - WCAG compliant with proper contrast and navigation

### **Dashboard Views**
- **Organizer Dashboard** - Committee overview with statistics and quick actions
- **Member Dashboard** - Personal contributions and payouts overview
- **Committee Detail** - Comprehensive committee information and member list
- **Reports Dashboard** - Generated reports with download capabilities

## 🔧 Configuration

### **Environment Variables (.env)**
```env
DEBUG=True
SECRET_KEY=your-secret-key-here
DATABASE_URL=sqlite:///db.sqlite3

# Email Configuration
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
EMAIL_PORT=587
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=your-email@gmail.com

# Celery Configuration
CELERY_BROKER_URL=amqp://localhost:5672
CELERY_RESULT_BACKEND=django-db
```

### **Settings Overview**
- **Database**: SQLite3 (production-ready PostgreSQL recommended)
- **Authentication**: Django Allauth with email-based login
- **File Storage**: Local media storage (AWS S3 recommended for production)
- **Task Queue**: Celery with RabbitMQ broker
- **Email**: SMTP backend with TLS support

## 🚀 Deployment

### **Production Checklist**
- [ ] Use PostgreSQL instead of SQLite3
- [ ] Configure proper SECRET_KEY
- [ ] Set DEBUG=False
- [ ] Configure ALLOWED_HOSTS
- [ ] Set up static files serving
- [ ] Configure media files storage (AWS S3/Cloudinary)
- [ ] Set up email backend (SendGrid/Mailgun)
- [ ] Configure Redis for Celery broker
- [ ] Set up monitoring and logging
- [ ] Configure SSL/TLS certificates
- [ ] Set up backup strategy

### **Docker Deployment** (Recommended)
```dockerfile
# Use official Python image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project
COPY . .

# Run migrations and collect static files
RUN python manage.py migrate
RUN python manage.py collectstatic --noinput

# Expose port
EXPOSE 8000

# Run the application
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "conf.wsgi:application"]
```

## 📚 API Documentation

### **Committee Endpoints**
```
GET    /committee/committees/           # List all committees
GET    /committee/<id>/                 # Committee details
POST   /committee/create/               # Create new committee
PUT    /committee/<id>/update/          # Update committee
DELETE /committee/<id>/delete/          # Delete committee
```

### **Member Endpoints**
```
GET    /committee/member-dashboard/     # Member dashboard
GET    /committee/member/committees/    # Member's committees
POST   /committee/member/contributions/ # Add contribution
GET    /committee/member/my-contributions/ # View contributions
GET    /committee/member/my-payouts/    # View payouts
```

### **Admin Endpoints**
```
GET    /admin/                          # Django admin panel
GET    /committee/organizer-dashboard/  # Organizer dashboard
POST   /committee/<id>/invite/          # Send invitation
GET    /committee/<id>/reports/         # Generate reports
```

## 🔒 Security Features

- **CSRF Protection** - All forms protected against CSRF attacks
- **Secure Passwords** - Django's robust password validation
- **File Upload Security** - Restricted file types and size limits
- **Email Verification** - Secure token-based email verification
- **Role-based Access** - Proper permission system for organizers vs members
- **Secure Headers** - Security middleware for production deployment

## 📈 Monitoring & Analytics

- **Django Admin** - Built-in admin interface for system monitoring
- **Celery Monitoring** - Task queue monitoring and management
- **Database Queries** - Query optimization and performance tracking
- **Error Logging** - Comprehensive error tracking and reporting

## 🤝 Contributing

We welcome contributions! Please follow these steps:

1. **Fork the repository**
2. **Create a feature branch** (`git checkout -b feature/amazing-feature`)
3. **Make your changes** and test thoroughly
4. **Commit your changes** (`git commit -m 'Add amazing feature'`)
5. **Push to the branch** (`git push origin feature/amazing-feature`)
6. **Open a Pull Request**

### **Development Guidelines**
- Follow Django best practices and PEP 8
- Write comprehensive tests for new features
- Update documentation for API changes
- Ensure responsive design for all new UI components

## 📄 License

This project is licensed under the **MIT License** - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Django Community** - For the excellent web framework
- **Tailwind CSS** - For the beautiful styling system
- **Celery Project** - For reliable background task processing
- **Django Allauth** - For robust authentication system

## 📞 Support

For support and questions:
- **Email**: support@smartcommittee.com
- **Documentation**: [Link to detailed docs]
- **Issues**: [GitHub Issues](https://github.com/your-username/Smart-Committee/issues)

---

**Built with ❤️ using Django, Tailwind CSS, and modern web technologies**
