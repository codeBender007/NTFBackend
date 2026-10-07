from sqlalchemy.orm import Session
from app.models.linesModel import Line
from app.schemas.linesSchema import LineCreate, LineUpdate

def getAllLines(db: Session, departmentId: int = None, subDepartmentId: int = None):
    query = db.query(Line)
    if departmentId:
        query = query.filter(Line.departmentId == departmentId)
    if subDepartmentId:
        query = query.filter(Line.subDepartmentId == subDepartmentId)
    return query.all()

def getLineById(db: Session, lineId: int):
    return db.query(Line).filter(Line.id == lineId).first()

def createLine(db: Session, lineData: LineCreate):
    newLine = Line(
        departmentId=lineData.departmentId,
        subDepartmentId=lineData.subDepartmentId,
        lineName=lineData.lineName
    )
    db.add(newLine)
    db.commit()
    db.refresh(newLine)
    return newLine

def updateLine(db: Session, lineId: int, lineData: LineUpdate):
    line = getLineById(db, lineId)
    if not line:
        return None
    if lineData.departmentId is not None:
        line.departmentId = lineData.departmentId
    if lineData.subDepartmentId is not None:
        line.subDepartmentId = lineData.subDepartmentId
    if lineData.lineName is not None:
        line.lineName = lineData.lineName
    db.commit()
    db.refresh(line)
    return line

def deleteLine(db: Session, lineId: int):
    line = getLineById(db, lineId)
    if not line:
        return None
    db.delete(line)
    db.commit()
    return line