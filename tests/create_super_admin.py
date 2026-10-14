import sys
from datetime import date
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import get_password_hash
from app.LMS.models.userModel import User

# Super Admin Default Credentials
SUPER_ADMIN_PAYCODE = "ADMIN-001"
SUPER_ADMIN_EMAIL = "superadmin@ntfauto.com"
SUPER_ADMIN_PASSWORD = "SuperAdmin@NTF2026"
SUPER_ADMIN_ROLE = "SUPER_ADMIN"

def create_super_admin():
    db: Session = SessionLocal()
    try:
        # Check karein ki user pehle se exist to nahi karta
        existing_admin = db.query(User).filter(
            (User.payCode == SUPER_ADMIN_PAYCODE) | (User.email == SUPER_ADMIN_EMAIL)
        ).first()

        if existing_admin:
            print("\n[!] Super Admin pehle se database me maujood hai:")
            print(f"    PayCode : {existing_admin.payCode}")
            print(f"    Email   : {existing_admin.email}")
            print(f"    Role    : {existing_admin.role}")
            print(f"    Status  : {'Active' if existing_admin.active else 'Inactive'}\n")
            return

        # Password hash generate karein
        hashed_pwd = get_password_hash(SUPER_ADMIN_PASSWORD)

        # Super Admin record prepare karein
        # (Hierarchy columns ko None rakha hai taaki ye kisi specific plant ya machine tak limit na ho)
        super_admin = User(
            payCode=SUPER_ADMIN_PAYCODE,
            cardNo="CRD-ADMIN-01",
            empName="System Super Administrator",
            dob=date(1990, 1, 1),
            dateOfJoining=date.today(),
            leavingDate=None,
            
            # Plant & Hierarchy (Global access ke liye None)
            plantId=None,
            plantLocation=None,
            departmentId=None,
            departmentName=None,
            subDepartmentId=None,
            subDepartmentName=None,
            lineId=None,
            lineName=None,
            machineId=None,
            machineName=None,

            shift="General",
            companyName="NTF Automobile Pvt Ltd",
            category="Management",
            grade="M1",
            designation="Super Admin",
            skillLevel="Level 4",
            isDojo=True,
            firstOfDay="Morning",

            gender="Male",
            bloodGroup="O+",
            fatherName="N/A",
            maritalStatus="Single",

            email=SUPER_ADMIN_EMAIL,
            mobileNo="+919999999999",
            address="Corporate Office, New Delhi",
            states="Delhi",
            pinCode="110001",

            bankAccount=None,
            salary=None,
            hra=None,
            pfNo=None,
            panNo=None,
            esiNo=None,
            aadharNo=None,

            passwordHash=hashed_pwd,
            role=SUPER_ADMIN_ROLE,
            active=True
        )

        db.add(super_admin)
        db.commit()
        db.refresh(super_admin)

        print("\n" + "=" * 50)
        print("    Super Admin Successfully Created!    ")
        print("=" * 50)
        print(f" PayCode  : {SUPER_ADMIN_PAYCODE}")
        print(f" Email    : {SUPER_ADMIN_EMAIL}")
        print(f" Password : {SUPER_ADMIN_PASSWORD}")
        print(f" Role     : {SUPER_ADMIN_ROLE}")
        print(f" User ID  : {super_admin.id}")
        print("=" * 50 + "\n")

    except Exception as e:
        db.rollback()
        print(f"\n[-] Super Admin creation failed: {str(e)}\n")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    create_super_admin()