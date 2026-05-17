class AcademicYearProvisionError(Exception):
    """Academic year row was committed; provisioning student year fees failed."""

    def __init__(self, year, cause: Exception):
        self.year = year
        super().__init__(str(cause))
