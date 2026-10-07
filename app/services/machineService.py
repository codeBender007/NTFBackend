from sqlalchemy.orm import Session
from app.models.machineModel import Machine
from app.schemas.machineSchema import MachineCreate, MachineUpdate

def getAllMachines(db: Session, departmentId: int = None, subDepartmentId: int = None, lineId: int = None):
    query = db.query(Machine)
    if departmentId:
        query = query.filter(Machine.departmentId == departmentId)
    if subDepartmentId:
        query = query.filter(Machine.subDepartmentId == subDepartmentId)
    if lineId:
        query = query.filter(Machine.lineId == lineId)
    return query.all()

def getMachineById(db: Session, machineId: int):
    return db.query(Machine).filter(Machine.id == machineId).first()

def createMachine(db: Session, machineData: MachineCreate):
    newMachine = Machine(
        departmentId=machineData.departmentId,
        subDepartmentId=machineData.subDepartmentId,
        lineId=machineData.lineId,
        machineName=machineData.machineName
    )
    db.add(newMachine)
    db.commit()
    db.refresh(newMachine)
    return newMachine

def updateMachine(db: Session, machineId: int, machineData: MachineUpdate):
    machine = getMachineById(db, machineId)
    if not machine:
        return None
    if machineData.departmentId is not None:
        machine.departmentId = machineData.departmentId
    if machineData.subDepartmentId is not None:
        machine.subDepartmentId = machineData.subDepartmentId
    if machineData.lineId is not None:
        machine.lineId = machineData.lineId
    if machineData.machineName is not None:
        machine.machineName = machineData.machineName
    db.commit()
    db.refresh(machine)
    return machine

def deleteMachine(db: Session, machineId: int):
    machine = getMachineById(db, machineId)
    if not machine:
        return None
    db.delete(machine)
    db.commit()
    return machine