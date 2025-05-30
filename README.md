# django-webadb

## Overview

django-webadb is a web application built with Django 5 for forensic data acquisition from Android devices. It allows investigators to manage cases, handle evidence, and perform various acquisition methods.

Key features include:
*   **Case Management:** Organize and manage forensic cases.
*   **Evidence Management:** Securely handle and track acquired evidence.
*   **Acquisition Methods:**
    *   Physical Acquisition (via USB/Wi-Fi)
    *   Selective Full File System Acquisition (via USB/Wi-Fi)

This project aims to provide a comprehensive and user-friendly tool for the DFIR (Digital Forensics and Incident Response) community, building upon the concepts of WebADB and RAAS (Remote Acquisition Android Smartphone) with enhanced capabilities.

## Features

-   **Case Management:** Create, update, and manage digital forensic cases.
-   **Evidence Management:** Track and manage evidence items, including a detailed chain of custody.
-   **Device Management:** List connected Android devices and view their detailed information.
-   **Data Acquisition:**
    -   Physical Acquisition: Perform full physical data extraction from Android devices (supports dd and E01 formats).
    -   Selective Full File System Acquisition: Acquire specific files and directories from the device's file system (uses TAR and Netcat).
    -   Wired (USB) and Wireless (Wi-Fi) Acquisition: Supports data acquisition through both USB and network connections.
    -   Asynchronous Operations: Long-running acquisition tasks are handled asynchronously using Celery.
-   **User Management:** Manage user accounts and roles within the application.
-   **Activity Logging:** Comprehensive logging of user actions and system events for audit trails.

## Getting Started

To begin using this app, follow these steps to set up your development environment:

Note: 
* I don't provide feature to root the device, so you need to root the device if you want to use the physical acquisition (but some basic task doesn't need root)
* Maybe some phone will not work with other features, because need some adjustment for the device
* I can say this forensically sound tool and still in the development stage for stable use

### Prerequisites

Also documented [here](https://s3.wasabisys.com/c343765-a/User-Manual/RAAS%20-%20User%20Manual%20v1.0.pdf) with  how to use. Or you can follow the instructions below to ensure the dependencies are installed on your system:

- **Python 3.10+**
- **SDK Platform Tools** (Add to your PATH)
- **pip** (Python package installer)
- **node.js** (Install [node.js](https://nodejs.org/en/download/) first if you don't have it in your machine, min version 18.0 for this package)
- **yarn** (Install [yarn](https://classic.yarnpkg.com/lang/en/docs/install/#windows-stable) first if you don't have it in your machine) for installing the frontend dependencies
- **Redis server** (You can install it on the same server)
- **Virtualenv** (Optional but recommended for creating isolated Python environments)
- **ewf-tools** (Tools for working with EWF files), you can install it with `sudo apt install ewf-tools`
- **netcat-openbsd** (For seamless device communication over the network), you can install it with `sudo apt install netcat-openbsd`

### For The Device
- You need to enable USB Debugging on your device and connect it to your computer via USB/IP Address
- And then you can check if the device is connected by running `adb devices` on your terminal

### Step-by-Step Setup Guide

1. **Clone the Repository or Extract the Source Code**:
    ```sh
    git clone [repository_url]    # or extract the folder
    cd django-webadb
    ```
2. **Install yarn packages for the frontend**:
    ```sh
    cd apps    # Go to the apps directory
    yarn install
    ```
3. **Create and Activate a Virtual Environment**:
    ```sh
    cd ..   # Go back to the root directory
    python3 -m venv venv
    source venv/bin/activate   # On Windows use `venv\Scripts\activate`
    ```

4. **Install Dependencies**:
    ```sh
    pip install -r requirements.txt
    ```

5. **Install Django and Set Up the Database**:
    ```sh
    python manage.py migrate
    ```

6. **Create a Superuser**: 
   To access the admin interface, you'll need a superuser account. Create one by running:
    ```sh
    python manage.py createsuperuser
    ```

7. **Collect Static Files**:
    ```sh
    python manage.py collectstatic
    ```

8. **Run the Server**:
    ```sh
    daphne core.asgi:application
    ```

9. **Run the Worker (New Terminal)**:
    ```sh
    cd django-webadb
    source venv/bin/activate   # On Windows use `venv\Scripts\activate`
    celery -A core worker --concurrency=3 -l info
    ```
   For the worker, you can adjust the concurrency parameter to your needs. This means that the worker will process 3 tasks concurrently. You can increase or decrease this number based on your system's capabilities.


10. **Access the Application**:
    Open your web browser and navigate to `http://127.0.0.1:8000/` to access the RAAS application. Use the superuser account to access the admin interface at `http://127.0.0.1:8000/admin/`.

## Todo List
- [x] Physical Acquisition (USB & Wireless)
- [x] Selective Full File System Acquisition [BETA] (USB & Wireless)
- [x] Case Management and Evidence Management (Improvements Implemented)
- [ ] Logical Acquisition
- [ ] Comprehensive Reporting System
- [ ] Advanced Log Management (View, Filter, Export)
- [ ] Ongoing Security Enhancements

## Running Tests

This project uses Django's built-in testing framework. Test files are located in `tests.py` within each application directory (e.g., `apps/authentication/tests.py`, `apps/home/tests.py`).

To run all tests, navigate to the project root directory (where `manage.py` is located) and execute the following command:

```sh
python manage.py test
```

You can also run tests for a specific application by appending the application name:

```sh
python manage.py test apps.home
python manage.py test apps.authentication
```

## Future Enhancements

I understand that this application is still less than perfect and that there are many aspects that need improvement. I will continue to work on developing it as effectively and efficiently as possible.

Stay tuned for more features that will be released next year. These features will enhance the capabilities of RAAS, providing more powerful tools for data acquisition and analysis.

## Contributing

We welcome contributions to django-webadb! If you'd like to contribute, please follow these steps:

1.  **Fork the repository** on GitHub.
2.  **Create a new branch** for your feature or bug fix:
    ```sh
    git checkout -b your-branch-name
    ```
3.  **Make your changes** and commit them with clear, descriptive messages.
4.  **Ensure all tests pass.** Run the test suite to confirm your changes haven't introduced regressions:
    ```sh
    python manage.py test
    ```
5.  **Push your branch** to your fork:
    ```sh
    git push origin your-branch-name
    ```
6.  **Submit a pull request** to the main django-webadb repository.

We appreciate your help in making this tool better!

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

Additionally, this project uses the Stisla dashboard template, which is also under the [MIT License](https://github.com/stisla/stisla/blob/master/LICENSE).
