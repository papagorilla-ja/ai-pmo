import json
import logging
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.models.calendar import CalendarHoliday
from app.schemas.calendar import CalendarHolidayCreate, CalendarHolidayUpdate, CalendarHolidayResponse, CalendarHolidaySyncRequest
from app.services.llm import llm_service
from app.core.deps import get_current_user
from app.models.resource import Resource

logger = logging.getLogger(__name__)
router = APIRouter()

@router.get("/holidays", response_model=List[CalendarHolidayResponse])
async def get_holidays(
    year: int = None,
    current_user: Resource = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    query = select(CalendarHoliday)
    if year is not None:
        query = query.where(CalendarHoliday.year == year)
    result = await db.execute(query)
    return result.scalars().all()

@router.post("/holidays", response_model=CalendarHolidayResponse, status_code=status.HTTP_201_CREATED)
async def create_holiday(
    holiday_in: CalendarHolidayCreate,
    current_user: Resource = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Authorization: only Managers and Admins can manage holidays
    if current_user.system_role not in ["管理者", "マネージャ"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="休日マスタの変更権限がありません。"
        )
    
    # Check if holiday on this date already exists
    existing = await db.execute(select(CalendarHoliday).where(CalendarHoliday.date == holiday_in.date))
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="この日付の休日は既に登録されています。"
        )
        
    db_holiday = CalendarHoliday(**holiday_in.model_dump())
    db.add(db_holiday)
    await db.commit()
    await db.refresh(db_holiday)
    return db_holiday

@router.put("/holidays/{holiday_id}", response_model=CalendarHolidayResponse)
async def update_holiday(
    holiday_id: str,
    holiday_in: CalendarHolidayUpdate,
    current_user: Resource = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.system_role not in ["管理者", "マネージャ"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="休日マスタの変更権限がありません。"
        )
        
    result = await db.execute(select(CalendarHoliday).where(CalendarHoliday.id == holiday_id))
    db_holiday = result.scalars().first()
    if not db_holiday:
        raise HTTPException(status_code=404, detail="休日が見つかりません。")
        
    update_data = holiday_in.model_dump(exclude_unset=True)
    for key, val in update_data.items():
        setattr(db_holiday, key, val)
        
    await db.commit()
    await db.refresh(db_holiday)
    return db_holiday

@router.delete("/holidays/{holiday_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_holiday(
    holiday_id: str,
    current_user: Resource = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.system_role not in ["管理者", "マネージャ"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="休日マスタの削除権限がありません。"
        )
        
    result = await db.execute(select(CalendarHoliday).where(CalendarHoliday.id == holiday_id))
    db_holiday = result.scalars().first()
    if not db_holiday:
        raise HTTPException(status_code=404, detail="休日が見つかりません。")
        
    await db.delete(db_holiday)
    await db.commit()
    return None

@router.post("/sync-public-holidays", response_model=List[CalendarHolidayResponse])
async def sync_public_holidays(
    request: CalendarHolidaySyncRequest,
    current_user: Resource = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    if current_user.system_role not in ["管理者", "マネージャ"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="祝祭日同期の実行権限がありません。"
        )
        
    year = request.year
    system_prompt = (
        "You are an assistant that outputs Japanese public holidays for a given year as a structured JSON list of objects. "
        "Each object must have keys 'date' (format 'YYYY-MM-DD') and 'name' (holiday name in Japanese). "
        "Do not include any conversational text, formatting wrappers, or explanation outside the JSON array. Output strictly the raw JSON array."
    )
    user_prompt = f"Output the Japanese public holidays for the year {year}."
    
    try:
        response_text = await llm_service.get_response(system_prompt, user_prompt, temperature=0.1)
        # Parse JSON from response
        # Clean potential markdown JSON block wrapper
        cleaned_text = response_text.strip()
        if cleaned_text.startswith("```"):
            lines = cleaned_text.split("\n")
            if lines[0].startswith("```json") or lines[0].startswith("```"):
                lines = lines[1:-1]
            cleaned_text = "\n".join(lines).strip()
            
        holidays_data = json.loads(cleaned_text)
        if not isinstance(holidays_data, list):
            raise ValueError("Expected a list of holidays")
            
        results = []
        for h in holidays_data:
            date_str = h.get("date")
            name_str = h.get("name")
            if date_str and name_str:
                # Upsert holiday
                query = select(CalendarHoliday).where(CalendarHoliday.date == date_str)
                existing_res = await db.execute(query)
                existing = existing_res.scalars().first()
                if existing:
                    existing.name = name_str
                    existing.year = year
                    existing.is_company_holiday = False
                    db_holiday = existing
                else:
                    db_holiday = CalendarHoliday(
                        date=date_str,
                        name=name_str,
                        is_company_holiday=False,
                        year=year
                    )
                    db.add(db_holiday)
                results.append(db_holiday)
                
        await db.commit()
        
        # Refresh all upserted items to return
        for r in results:
            await db.refresh(r)
            
        return results
        
    except Exception as e:
        logger.error(f"Failed to sync public holidays with LLM: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"祝日の自動生成に失敗しました: {str(e)}"
        )
