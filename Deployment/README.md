# ACE School Management — User Guide

**ACE School Management** is an offline desktop application for ACE High School. It helps staff manage student records, collect school and van fees, track salaries and expenses, run collection reports, and keep the school database safe with automatic backups.

This document is the main reference for school staff and administrators. Use it when learning the software, performing daily tasks, or fixing common problems.

---

## Table of contents

1. [Overview](#1-overview)
2. [System requirements](#2-system-requirements)
3. [Installing and opening the app](#3-installing-and-opening-the-app)
4. [Where your data is stored](#4-where-your-data-is-stored)
5. [Signing in and user roles](#5-signing-in-and-user-roles)
6. [Application layout](#6-application-layout)
7. [Daily workflows](#7-daily-workflows)
8. [Feature guide (by section)](#8-feature-guide-by-section)
9. [Academic years and fee rollover](#9-academic-years-and-fee-rollover)
10. [Backup and restore](#10-backup-and-restore)
11. [Passwords and account recovery](#11-passwords-and-account-recovery)
12. [Reports and exports](#12-reports-and-exports)
13. [Troubleshooting](#13-troubleshooting)
14. [Frequently asked questions](#14-frequently-asked-questions)

---

## 1. Overview

### What the app does

| Area | What you can do |
|------|-----------------|
| **Students** | Search, view, and add students; see fee balances per academic year |
| **Fee collection** | Record school and van fee payments; print PDF receipts |
| **Payment history** | Review past payments; undo mistakes; export to Excel |
| **Expenses** | Pay faculty salaries, record miscellaneous expenses, manage other income |
| **Admin control** | Set class fees and van fees, add faculty, manage login passwords |
| **Reports** | List students with pending fees; export to Excel or PDF |
| **Backup** | Automatic daily backups plus manual backup and restore |
| **Dashboard** | Summary of collections, expenses, and key metrics |

### Important facts

- **Works fully offline** — no internet is required after installation.
- **No installation needed** — the app is a single program file. There is nothing to install, and no Python or other software is required.
- **Single computer database** — all records are stored locally on the PC where the app runs.
- **One instance at a time** — if you open the app twice, the second window brings the first one to the front instead of opening a duplicate.
- **Automatic updates to the database** — the app applies any needed database updates each time it starts.

---

## 2. System requirements

| Requirement | Details |
|-------------|---------|
| **Operating system** | Windows 10 or Windows 11 (64-bit recommended) |
| **Disk space** | At least 500 MB free (more if you keep many backups) |
| **Screen** | 1360×860 or larger recommended |
| **Internet** | Not required for daily use |
| **Other software** | None — no Python, database server, or browser needed |

See `requirements.txt` for the full minimum and recommended hardware specifications.

---

## 3. Installing and opening the app

1. Copy **`ACE School Management.exe`** to a folder on the school computer (for example `C:\ACE School Management\` or the Desktop).
2. Double-click **`ACE School Management.exe`** to start.
3. **Pin to taskbar** (optional): right-click the exe → **Pin to taskbar** for quick access.
4. On first launch, the app creates its data folder automatically (see [Section 4](#4-where-your-data-is-stored)).

> **Tip:** Keep the `.exe` in a stable location. Moving it later is fine — your data is stored separately and will be found automatically.

### First launch checklist

- [ ] App opens to the login screen with the school logo and name
- [ ] Sign in with the **Administrator** account (see [Section 5](#5-signing-in-and-user-roles))
- [ ] Change the default passwords after first login (see [Section 11](#11-passwords-and-account-recovery))
- [ ] Confirm a backup folder exists (open **Backup** in the sidebar)
- [ ] Set up the current **academic year** and **class fees** if not already configured

---

## 4. Where your data is stored

All school records live in a single database file on the computer. Backups and configuration files are kept alongside it. The app creates and manages this folder for you automatically.

| Item | Location |
|------|----------|
| **Live database** | `%LOCALAPPDATA%\ACE School Management\fee_management.db` |
| **Backups** | `%LOCALAPPDATA%\ACE School Management\backups\` |
| **Master key** (password recovery) | `%LOCALAPPDATA%\ACE School Management\master_key.txt` |
| **School name override** (optional) | `%LOCALAPPDATA%\ACE School Management\school_name.txt` |

To open the data folder quickly:

1. Press **Win + R**
2. Type: `%LOCALAPPDATA%\ACE School Management`
3. Press **Enter**

### Custom school name

To display a different name in the app window and login screen, create a text file named **`school_name.txt`** in the data folder with the school name on a single line.

---

## 5. Signing in and user roles

### Default accounts

On first run, two accounts are created automatically:

| Account | Default password | Role | Access |
|---------|------------------|------|--------|
| **Admin** | `Admin@1123` | Administrator | Full access to every section |
| **Accountant** | `Acc@123` | Accountant | **Collect Payment**, **Miscellaneous**, and **Income Management** |

> **Security:** Change these passwords immediately after installation. See [Section 11](#11-passwords-and-account-recovery).

### Administrator

The Administrator can:

- View the dashboard and all reports
- Add and edit students and faculty
- Collect fees and manage payment history
- Set class fees, van fees, and salary rates
- Manage academic years
- Reset user passwords
- Create and restore backups

### Accountant

The Accountant has a simplified menu with only:

- **Collect Payment** — record student fee payments
- **Miscellaneous** — record school expenses (cannot edit or delete entries after saving)
- **Income Management** — record non-fee income (cannot edit or delete entries after saving)

Accountants cannot view student lists, reports, backups, or admin settings. Only an Administrator can modify or delete recorded expense and income entries.

### Signing in

1. Open the app.
2. Select **Admin** or **Accountant** at the top of the login form.
3. Enter the password.
4. Click **Sign in** (or press **Enter**).

### Signing out

Click **Log out** at the bottom of the left sidebar. The login screen appears so another user can sign in without closing the app.

### Light / dark theme

Use the theme toggle at the bottom of the sidebar to switch between light and dark mode. Your preference is remembered.

---

## 6. Application layout

After login, the main window has:

- **Left sidebar** — navigation grouped by area (Dashboard, Students, Fees, Expenses, Admin, Reports, Backup)
- **Top area** — page title and breadcrumbs showing where you are
- **Main content** — tables, forms, and action buttons for the selected page

### Navigation map (Administrator)

```
Dashboard
Students
  ├── Student List
  └── Student Details
Fees Collection
  ├── Collect Payment
  └── Payment History
Expenses
  ├── Salary
  ├── Salary History
  ├── Miscellaneous
  └── Income Management
Admin Control
  ├── Add New Student
  ├── Add Faculty
  ├── Salary Control
  ├── Fee Control
  └── Login Access
Reports
Backup
```

### Navigation map (Accountant)

```
Collect Payment
Miscellaneous
Income Management
```

---

## 7. Daily workflows

### Collect a fee payment

1. Go to **Fees Collection → Collect Payment**.
2. Search for the student by ID, name, or phone number.
3. Select the student from the results.
4. Review the fee breakdown (school fees, van fees, pending amounts).
5. Enter the payment amount, payment mode, and date.
6. Click **Collect** to record the payment.
7. Optionally click **Print Receipt** to save a PDF receipt.

### Look up a student’s balance

1. Go to **Students → Student List**.
2. Search by student ID, name, or phone.
3. Review columns such as **Pending fees**, **School Due**, **Van Due**, and **Total Due**.
4. For full year-by-year detail, select the student and open **Students → Student Details**.

### Add a new student

1. Go to **Admin Control → Add New Student**.
2. Fill in all required fields (marked with *).
3. Select class, section, village (for van fee), and contact details.
4. Click **Add Student**.

### Pay faculty salary

1. Go to **Expenses → Salary**.
2. Select the faculty member and month.
3. Enter attendance/working days if applicable.
4. Confirm the calculated amount and record the payment.

### Check who has not paid

1. Go to **Reports**.
2. Optionally filter by class, section, village, or fee status.
3. Click **Load** to refresh the defaulter list.
4. Export to **Excel** or **PDF** if needed.

### End-of-day backup (optional but recommended)

The app already creates one automatic backup per day on first launch. For extra safety before major changes:

1. Go to **Backup**.
2. Click **Create backup now**.
3. Confirm the new file appears in the backup list.

---

## 8. Feature guide (by section)

### Dashboard (Home Page)

The dashboard shows:

- Current academic year
- Student counts and collection summaries
- Charts for fee collection, expenses, and income over time

Use the chart month/year controls to change the period. Links and buttons on the dashboard can jump you to related sections (for example, managing academic years).

---

### Students → Student List

Search and browse all students in a detailed table.

**Search tips:**

- Search by student ID, full name, or mobile number
- Use column headers to sort
- Use filters for class, section, village, and status
- Export the current list to Excel with **Export Excel**

**Key columns:**

| Column | Meaning |
|--------|---------|
| Pending fees | Carried-forward balance from previous years |
| School Due (current) | Unpaid school fee for the current academic year |
| Van Due (current) | Unpaid van/transport fee for the current year |
| Total Due | Combined amount still owed |

---

### Students → Student Details

View and edit a single student’s profile and fee history across academic years. Select a student from **Student List** first, or search within this page.

---

### Fees Collection → Collect Payment

Record payments against a student’s outstanding balance. The system allocates payment across fee heads (school, van, pending) according to business rules built into the app.

After collection:

- A unique **reference number** is assigned to the payment
- The student’s due amounts update immediately
- You can print a PDF receipt from the payment dialog or from **Payment History**

---

### Fees Collection → Payment History

View all recorded fee payments with filters.

| Action | Description |
|--------|-------------|
| **Search / filter** | Find payments by reference, student, date, etc. |
| **Print receipt** | Generate a PDF for an existing payment |
| **Undo** | Reverse a payment that was recorded by mistake (requires confirmation) |
| **Export Excel** | Download payment history for accounting |

> **Undo caution:** Undo permanently removes the payment record and restores the student’s balance. Only use this for genuine errors.

---

### Expenses → Salary

Record monthly salary payouts for teaching and non-teaching faculty. Amounts can be adjusted based on attendance and working days.

---

### Expenses → Salary History

Review past salary payments. You can **Undo** an incorrect salary payout (same caution as payment undo) and **Export Excel** for records.

---

### Expenses → Miscellaneous

Record day-to-day school expenses that are not salaries (for example supplies, maintenance).

---

### Expenses → Income Management

Record income that is not student fee collection (for example donations, grants, other receipts). Available to both Administrator and Accountant roles.

---

### Admin Control → Add Faculty

Add teaching or non-teaching staff with salary details, contact information, and role.

---

### Admin Control → Salary Control

Set or update the monthly salary rate and default working days for each faculty member.

---

### Admin Control → Fee Control

Configure fee amounts for the school.

**School fees (per class, per academic year):**

1. Select the academic year.
2. Enter or update the annual school fee for each class (LKG through Class 10).
3. Click **Apply** next to each class to save.

**Van fees (per village):**

- Van/transport fees are set per village name and apply globally (not per academic year).
- Update amounts in the Van Fees section of Fee Control.

**Locked years:** Once an academic year has ended, its class fee tariffs cannot be changed.

---

### Admin Control → Login Access

Administrator-only page to reset passwords for **Admin** or **Accountant** without needing the master key (you must already be signed in as Admin).

---

### Reports

Generate lists of students filtered by fee status:

- Pending / due amounts for the current year
- Fully paid students
- Custom filters by class, section, village, and search text

Click **Load** to refresh, then **Export Excel** or **Export PDF**.

---

### Backup

Manage database safety copies.

| Feature | Description |
|---------|-------------|
| **Automatic daily backup** | Created the first time you open the app each day |
| **Create backup now** | Manual snapshot at any time |
| **Restore** | Replace current data with a chosen backup (app restarts automatically) |
| **Delete** | Remove old backups to free disk space (the 4 newest are protected) |

The page shows the live database path, backup count, last backup time, and total storage used.

---

## 9. Academic years and fee rollover

### How academic years work

- Each academic year runs from **31 May** through **1 June** of the following calendar year.
  - Example: **2025–2026** = 31 May 2025 → 1 June 2026
- The year that contains **today’s date** is the **current academic year** for new fees and payments.
- School fee tariffs are set **per class, per academic year** in **Fee Control**.

### Adding a new academic year

1. Open **Fee Control** (or use **Manage academic years** on the dashboard / fee control page).
2. Click **Manage academic years**.
3. Click **Add next year** to create the next sequential year with correct dates and label.

### What happens when you add a forward year

| Event | Result |
|-------|--------|
| **Class promotion** | Every active student moves up one class (LKG→UKG→1→2→…→10) |
| **Class 10 students** | Marked **Passed Out** and set to inactive |
| **Pending fees** | New opening pending = existing pending + previous year school due + previous year van due |
| **Fee tariffs** | Copied from the previous year’s class fees (you can adjust before the year starts) |
| **Student fee rows** | New per-year fee records created for all active students |

> **Plan ahead:** Set class fees for the new year in **Fee Control** before heavy collection begins. Review promoted students and pending balances after rollover.

### Deleting an academic year

Only delete a year if it was added by mistake and has no important data. Select the year in **Manage academic years** and click **Delete year**. Confirm carefully — this cannot be undone except by restoring a backup.

---

## 10. Backup and restore

### Why backups matter

The entire school database is one file. Backups protect against:

- Accidental deletion of records
- Wrong payment or undo operations
- Hard drive failure (if backups are copied to another drive)
- Failed restore attempts (a pre-restore safety copy is always made)

### Automatic backups

- **When:** First app launch of each calendar day
- **Where:** `backups\` folder inside your data directory
- **Naming:** `fee_management_YYYYMMDD_HHMMSS.db`

### Manual backup

In the app: Backup → **Create backup now**

### Protected backups

The **4 most recent** backup files cannot be deleted from the app. This prevents accidental removal of your only recent safety copies. Older backups can be deleted to save space.

### Restoring a backup

1. Go to **Backup**.
2. Select a backup from the list (or use **Restore from file** to pick an external copy).
3. Read the warning — restore **replaces all current data**.
4. Click restore and confirm.
5. Click **Proceed** when prompted — the app closes and reopens with the restored data.

**Before every restore**, the app automatically saves your current database as `fee_management_pre_restore_YYYYMMDD_HHMMSS.db` in the backups folder.

### Copying backups to external storage

For disaster recovery, periodically copy the entire `backups` folder (or at least the newest `.db` file) to:

- An external USB drive
- Another computer on the school network
- Cloud storage (if school policy allows)

---

## 11. Passwords and account recovery

### Changing a password (while signed in as Admin)

1. Go to **Admin Control → Login Access**.
2. Select **Admin** or **Accountant**.
3. Enter and confirm the new password (minimum 6 characters).
4. Click **Reset password**.

### Forgot password (locked out of login)

1. On the login screen, click **Forgot password?**
2. Select the account (**Admin** or **Accountant**).
3. Enter the **master key** from `master_key.txt` in your data folder (see [Section 4](#4-where-your-data-is-stored)).
4. Enter and confirm the new password.
5. Sign in with the new password.

The master key file is created automatically on first app launch. **Store a copy in a secure place** (school safe, principal’s locked drawer, etc.). Only trusted senior staff should know this key.

### Password rules

- Minimum **6 characters**
- Passwords are stored securely (hashed) in the database — they cannot be read back, only reset

---

## 12. Reports and exports

### Available exports

| Location | Format | Contents |
|----------|--------|----------|
| **Reports** | Excel, PDF | Student fee status / defaulter lists |
| **Student List** | Excel | Full student table with fee columns |
| **Payment History** | Excel | Fee payment records (optional academic year filter) |
| **Salary History** | Excel | Faculty salary payout records |
| **Miscellaneous / Income** | Excel | Expense and income records |
| **Collect Payment / Payment History** | PDF | Individual payment receipts |

Exported files are saved where you choose in the standard Windows **Save** dialog (typically Downloads or Desktop).

---

## 13. Troubleshooting

### App will not open / nothing happens

| Check | Action |
|-------|--------|
| Already running? | Look for the app on the taskbar. Opening it again should bring the window forward. |
| Blocked by antivirus | Add `ACE School Management.exe` to your antivirus allow list. |
| Corrupt copy | Re-copy the `.exe` from the original distribution. Your data folder is separate and will not be deleted. |

### “Second instance” behaviour

Only one copy of the app runs at a time. If you double-click the exe while it is already open, the existing window is activated. This is normal and prevents database conflicts.

### Login fails / wrong password

1. Check **Caps Lock**.
2. Confirm you selected the correct account (**Admin** vs **Accountant**).
3. Use **Forgot password?** with the master key from `master_key.txt`.
4. If an Administrator is signed in on another session, reset the password from **Login Access**.

### App opened but data looks empty or old

- You may be on a new computer with a fresh database. Restore from a backup (see [Section 10](#10-backup-and-restore)).
- Confirm you are looking at the correct data folder (see [Section 4](#4-where-your-data-is-stored)).

### Restore did not show expected data

- The app **must restart** after restore. Use the in-app **Proceed** button, or close and reopen manually.
- Verify you selected the correct backup file (check date and time in the filename).

### Database locked / cannot save changes

| Cause | Fix |
|-------|-----|
| Second app instance | Close all copies; open only one |
| External tool has DB open | Close DB Browser, Excel, or any tool accessing `fee_management.db` |
| Stale lock after crash | Fully close the app and reopen. If needed, restart the computer. |

### Payment or salary recorded incorrectly

1. Go to **Payment History** or **Salary History**.
2. Find the entry by reference number.
3. Click **Undo** and confirm.
4. Re-enter the correct payment.

### Student balance looks wrong

- Check **Student Details** for year-by-year breakdown.
- Confirm the correct **academic year** is active.
- Verify **Fee Control** tariffs for that year.
- Check whether a payment was undone or a restore was performed recently.

### Academic year / promotion issues

- Open **Manage academic years** and confirm the current year includes today’s date.
- After adding a new year, review a sample of students for correct class promotion and pending fee amounts.
- If rollover was done incorrectly, restore the pre-rollover backup.

### Export or receipt PDF fails

- Ensure you have write permission to the chosen save folder.
- Try saving to **Desktop** or **Documents**.
- Confirm the file name does not contain invalid characters.

### Backup delete button disabled

The **4 newest** backups are protected and cannot be deleted. Choose an older backup to delete, or move old files manually after copying them elsewhere.

### School name or logo wrong

- **Name:** Create or edit `school_name.txt` in the data folder (one line, school name only). Restart the app.
- **Logo:** Contact your software provider — the logo is bundled with the application.

### Error messages mentioning “integrity” or “damaged backup”

The selected backup file is corrupt or incomplete. Choose a different (older) backup. Never delete all backups at once.

---

## 14. Frequently asked questions

**Q: Do I need internet to use the app?**  
A: No. After installation, everything runs offline.

**Q: Do I need to install Python or any other software?**  
A: No. Everything the app needs is bundled inside `ACE School Management.exe`. Just copy it and double-click.

**Q: Can multiple staff use the app at the same time on different computers?**  
A: Each installation has its own local database. This version does not sync between PCs. Use one primary computer for live operations, or establish a manual process to restore backups on a second machine (not recommended for concurrent use).

**Q: Can I move the app to a new computer?**  
A: Yes. Copy `ACE School Management.exe` to the new PC and copy your entire data folder (`%LOCALAPPDATA%\ACE School Management`) to the same path on the new PC. Or copy the newest backup and restore it on a fresh install.

**Q: How often should I back up?**  
A: The app backs up daily automatically. Also create a manual backup before academic year rollover, bulk imports, or major data cleanup.

**Q: What if my computer’s hard drive fails?**  
A: Recover from the most recent backup file stored on external media. Regular off-site backup copies are strongly recommended.

**Q: Who should have Administrator access?**  
A: Only the principal, office head, or trusted senior admin staff. Day-to-day fee collection can use the Accountant account.

**Q: What is the master key for?**  
A: Emergency password recovery when everyone has forgotten the Admin or Accountant password. Guard it like a physical key to the office.

**Q: Does deleting the app delete my data?**  
A: The data in `%LOCALAPPDATA%\ACE School Management` is not automatically removed when you delete the `.exe`. Keep that folder safe until you intentionally migrate or archive it.

---

## Document information

| | |
|--|--|
| **Application** | ACE School Management |
| **School** | ACE High School — *Aiming for Excellence* |
| **Platform** | Windows desktop (offline) |
| **Database** | SQLite (local file) |

For issues not covered in this guide, contact your software support provider with:

- A description of what you were trying to do
- The exact error message (screenshot helps)
- The location of your data folder and most recent backup file

---

*Keep this document with your installation media and backup procedures. Review the [Backup and restore](#10-backup-and-restore) section at least once per term.*
