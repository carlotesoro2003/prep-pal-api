from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import Optional
import time
import subprocess
import tempfile
import os
import signal
import logging

import services, models, schemas
from db import get_db
from auth import get_current_user


router = APIRouter()


# User Answers CRUD Endpoints
@router.post("/answers", response_model=schemas.UserAnswerResponse)
def create_answer(
    answer: schemas.UserAnswerCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    print("Received answer submission:", answer)
    try:
        db_answer = services.create_user_answer(db, answer, current_user.id)
        return db_answer
    except ValueError as e:
        print("ValueError:", e)
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        print("Exception:", e)
        raise HTTPException(status_code=500, detail=f"Failed to create answer: {str(e)}")
    

@router.get("/answers/{answer_id}", response_model=schemas.UserAnswerResponse)
def get_user_answer(
    answer_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get a specific user answer"""
    answer = services.get_user_answer_by_id(db, answer_id)
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")
    if answer.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this answer")
    return answer

@router.put("/answers/{answer_id}", response_model=schemas.UserAnswerResponse)
def update_user_answer(
    answer_id: int,
    answer_update: schemas.UserAnswerUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Update a user answer"""
    answer = services.get_user_answer_by_id(db, answer_id)
    if not answer:
        raise HTTPException(status_code=404, detail="Answer not found")
    if answer.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this answer")
    updated = services.update_user_answer(db, answer_id, answer_update)
    return updated

@router.get("/my-answers", response_model=schemas.UserAnswerListResponse)
def get_my_answers(
    question_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Get all answers submitted by the current user"""
    answers, total = services.get_user_answers(
        db,
        user_id=current_user.id,
        question_id=question_id
    )
    return {
        "answers": answers,
        "total": total,
        "page": 1,
        "per_page": total,
        "total_pages": 1
    }



@router.post("/code/run", response_model=schemas.CodeExecutionResponse)
async def run_code(
    request: schemas.CodeExecutionRequest = Body(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    """Execute code against test cases"""
    try:
        logging.info(f"Received /code/run request: language={request.language}, function_name={getattr(request, 'function_name', None)}")
        results = []
        # Use the provided time_limit or default to 5 seconds
        time_limit = getattr(request, "time_limit", 5)
        for idx, test_case in enumerate(request.test_cases):
            logging.info(f"Test case {idx+1}: input={test_case.get('input_data', '')}, expected_output={test_case.get('expected_output', '')}")
            if not getattr(request, "function_name", None):
                logging.error("function_name is missing in request")
                raise HTTPException(status_code=400, detail="function_name is required")
            result = await execute_code_safely(
                code=request.code,
                language=request.language,
                input_data=test_case.get("input_data", ""),
                expected_output=test_case.get("expected_output", ""),
                function_name=request.function_name,
                timeout=time_limit  # Use the time limit per question
            )
            logging.info(f"Test case {idx+1} result: {result}")
            results.append(result)

        logging.info(f"Returning results for code run: {results}")
        return {"results": results}
    except Exception as e:
        logging.exception("Exception during code run")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
    
async def execute_code_safely(code: str, language: str, input_data: str, function_name: str, expected_output: str, timeout: int = 5):
    """Execute code with proper error handling and security"""
    start_time = time.time()
    logging.info(f"Executing code safely: language={language}, function_name={function_name}, input_data={input_data}")
    try:
        if language == "python":
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                modified_code = f"""
import sys
import json
import inspect

# User's code
{code}

# Process input
try:
    input_data = '''{input_data}'''
    if input_data.strip():
        import json
        try:
            parsed_input = json.loads(input_data)
        except:
            parsed_input = [x.strip() for x in input_data.split(',')]

        def try_num(x):
            try:
                return int(x)
            except:
                try:
                    return float(x)
                except:
                    return x

        if isinstance(parsed_input, list):
            parsed_input = [try_num(x) for x in parsed_input]
        else:
            parsed_input = [try_num(parsed_input)]

        sig = inspect.signature({function_name})


        # Log the type of the first parameter if only one
        if len(sig.parameters) == 1:
            param_name = list(sig.parameters.keys())[0]


        # Decision logic for argument passing
        # If only one parameter and input is a list, pass as a single argument
        if len(sig.parameters) == 1 and isinstance(parsed_input, list):
            result = {function_name}(parsed_input)
        else:
            result = {function_name}(*parsed_input)
        print(json.dumps(result) if not isinstance(result, str) else result)
    else:
        exec(compile('''{code}''', '<string>', 'exec'))
except Exception as e:
    print(f"Error: {{e}}", file=sys.stderr)
    sys.exit(1)
"""
                logging.info(f"Generated Python code for execution:\n{modified_code}")
                f.write(modified_code)
                temp_file = f.name

            process = subprocess.Popen(
                ["python", temp_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                preexec_fn=os.setsid if os.name != 'nt' else None
            )

            try:
                stdout, stderr = process.communicate(timeout=timeout)
                actual_output = stdout.strip()
                error_message = stderr.strip() if stderr else None
                logging.info(f"Python execution output: {actual_output}")
                logging.info(f"Python execution error: {error_message}")
                os.unlink(temp_file)
            except subprocess.TimeoutExpired:
                logging.error("Python code execution timed out")
                if os.name != 'nt':
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                else:
                    process.terminate()
                process.wait()
                os.unlink(temp_file)
                return {
                    "input": input_data,
                    "expected_output": expected_output,
                    "actual_output": "",
                    "passed": False,
                    "execution_time": timeout * 1000,
                    "memory_usage": 0,
                    "error_message": "Time limit exceeded"
                }
        elif language == "javascript":
            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
                modified_code = f"""
const input_data = `{input_data}`;

// User's code
{code}

// Try to execute main function if exists
try {{
    if (typeof main === 'function') {{
        let parsedInput;
        try {{
            parsedInput = JSON.parse(input_data);
        }} catch {{
            parsedInput = input_data.trim();
        }}
        const result = main(parsedInput);
        console.log(typeof result === 'string' ? result : JSON.stringify(result));
    }} else {{
        // Look for any function and try to call it
        const functionMatch = `{code}`.match(/function\\s+(\\w+)\\s*\\([^)]*\\)/);
        if (functionMatch) {{
            const functionName = functionMatch[1];
            let parsedInput;
            try {{
                parsedInput = JSON.parse(input_data);
            }} catch {{
                parsedInput = input_data.trim();
            }}
            const result = eval(`${{functionName}}(parsedInput)`);
            console.log(typeof result === 'string' ? result : JSON.stringify(result));
        }}
    }}
}} catch (e) {{
    console.error('Error:', e.message);
    process.exit(1);
}}
"""
                logging.info(f"Generated JS code for execution:\n{modified_code}")
                f.write(modified_code)
                temp_file = f.name

            process = subprocess.Popen(
                ["node", temp_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                preexec_fn=os.setsid if os.name != 'nt' else None
            )

            try:
                stdout, stderr = process.communicate(timeout=timeout)
                actual_output = stdout.strip()
                error_message = stderr.strip() if stderr else None
                logging.info(f"JS execution output: {actual_output}")
                logging.info(f"JS execution error: {error_message}")
                os.unlink(temp_file)
            except subprocess.TimeoutExpired:
                logging.error("JS code execution timed out")
                if os.name != 'nt':
                    os.killpg(os.getpgid(process.pid), signal.SIGTERM)
                else:
                    process.terminate()
                process.wait()
                os.unlink(temp_file)
                return {
                    "input": input_data,
                    "expected_output": expected_output,
                    "actual_output": "",
                    "passed": False,
                    "execution_time": timeout * 1000,
                    "memory_usage": 0,
                    "error_message": "Time limit exceeded"
                }
        else:
            logging.error(f"Language {language} not supported")
            return {
                "input": input_data,
                "expected_output": expected_output,
                "actual_output": "",
                "passed": False,
                "execution_time": 0,
                "memory_usage": 0,
                "error_message": f"Language {language} not supported"
            }

        execution_time = int((time.time() - start_time) * 1000)  # Convert to ms

        # Compare outputs (normalize whitespace)
        actual_normalized = actual_output.strip()
        expected_normalized = expected_output.strip()
        passed = actual_normalized == expected_normalized

        logging.info(f"Test result: passed={passed}, actual_output={actual_output}, expected_output={expected_output}")

        return {
            "input": input_data,
            "expected_output": expected_output,
            "actual_output": actual_output,
            "passed": passed,
            "execution_time": execution_time,
            "memory_usage": 0,  # Would need system monitoring for real memory usage
            "error_message": error_message
        }

    except Exception as e:
        logging.exception("Exception during safe code execution")
        return {
            "input": input_data,
            "expected_output": expected_output,
            "actual_output": "",
            "passed": False,
            "execution_time": 0,
            "memory_usage": 0,
            "error_message": str(e)
        }