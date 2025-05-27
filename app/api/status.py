"""
Status API Endpoints

This module contains API endpoints for monitoring crawl session status
including both SSE and polling implementations.
"""

import json
import queue
from flask import Blueprint, jsonify, Response

from app.config import Config
from app.models.session import session_manager
from app.services.cache import cache_service

# Create blueprint
status_bp = Blueprint('status', __name__)


@status_bp.route('/crawl/<session_id>/status')
def crawl_status_sse(session_id):
    """
    Server-Sent Events endpoint for real-time crawl status updates.
    
    This endpoint provides a continuous stream of status updates for a
    crawling session. Clients can subscribe to receive real-time progress.
    
    Args:
        session_id (str): The session ID to monitor
        
    Returns:
        SSE stream with status updates or redirect to polling endpoint
        
    Error Codes:
        404: Session not found
        503: SSE disabled, use polling endpoint
    """
    if not Config.ENABLE_SSE:
        return jsonify({
            "error": "SSE disabled", 
            "message": "Use polling endpoint instead",
            "polling_url": f"/crawl/{session_id}/status-simple"
        }), 503
    
    session = session_manager.get_session(session_id)
    
    if not session:
        return jsonify({"error": "Session not found"}), 404

    def generate():
        """
        Generator function for Server-Sent Events.
        
        This function yields status messages from the session's message queue
        and handles connection lifecycle (heartbeats, completion detection).
        """
        try:
            # Check if cache is available
            cache_available = cache_service.is_available()
            
            # Send initial connection confirmation with detailed cache status
            initial_message = {
                'type': 'connected', 
                'session_id': session_id,
                'cache_available': cache_available,
                'skip_cache': session.skip_cache if hasattr(session, 'skip_cache') else False
            }
            
            # Add cache performance metrics if available
            if cache_available:
                cache_stats = {}
                try:
                    # Get overall cache stats
                    cache_stats = cache_service.metrics.get_performance_stats()
                    if cache_stats:
                        # Add summary of cache performance
                        initial_message['cache_stats'] = {
                            'hit_rates': {
                                'html': cache_stats.get('html_cache', {}).get('hit_rate', 0),
                                'query': cache_stats.get('query_cache', {}).get('hit_rate', 0),
                                'embedding': cache_stats.get('embedding_cache', {}).get('hit_rate', 0)
                            },
                            'overall_hit_rate': cache_stats.get('overall', {}).get('overall_hit_rate', 0),
                            'total_hits': sum(c.get('total_hits', 0) for c in cache_stats.values() if isinstance(c, dict)),
                            'performance_gains': {
                                'html': '~85% faster',
                                'query': '~90% faster',
                                'embedding': '~70% faster'
                            }
                        }
                except Exception:
                    pass
            yield f"data: {json.dumps(initial_message)}\n\n"
            
            # Timeout counter to prevent infinite connections
            max_duration = Config.SSE_TIMEOUT_SECONDS
            heartbeat_count = 0
            
            # Main message loop
            while heartbeat_count < max_duration:
                try:
                    # Wait for new message (1 second timeout)
                    message = session.messages.get(timeout=1)
                    
                    # Enhance message with cache info if applicable
                    if message['type'] == 'progress' and hasattr(session, 'cache_hits') and session.cache_hits > 0:
                        if 'cache_hit' not in message['data']:
                            message['data']['cache_hit'] = True
                            message['data']['cache_hits'] = session.cache_hits
                            

                    
                    # Send the message
                    yield f"data: {json.dumps(message)}\n\n"
                    
                    # Close connection if crawl is finished (success or error)
                    if message.get('type') in ['completed', 'error']:
                        break
                        
                except queue.Empty:
                    # No new messages - send heartbeat to keep connection alive
                    heartbeat_count += 1
                    yield f"data: {json.dumps({'type': 'heartbeat', 'time': heartbeat_count})}\n\n"
                    
                    # Check if session has finished (failsafe)
                    if session.completed or session.error:
                        # Send final status if available
                        final_message = {
                            'type': 'completed' if session.completed else 'error',
                            'status': 'completed' if session.completed else 'error'
                        }
                        
                        if session.error:
                            final_message['message'] = session.error
                            
                        # Add cache information to final message
                        if session.completed and hasattr(session, 'cache_hits') and session.cache_hits > 0:
                            final_message['cache_hits'] = session.cache_hits
                            
                        yield f"data: {json.dumps(final_message)}\n\n"
                        break
                
                except Exception as e:
                    # Handle any other exceptions gracefully
                    yield f"data: {json.dumps({'type': 'error', 'message': f'SSE error: {str(e)}'})}\n\n"
                    break
            
            # Send timeout message if we reach max duration
            if heartbeat_count >= max_duration:
                timeout_minutes = max_duration // 60
                yield f"data: {json.dumps({'type': 'timeout', 'message': f'Connection timeout after {timeout_minutes} minutes'})}\n\n"
                
        except Exception as e:
            # Final safety net for any generator errors
            try:
                yield f"data: {json.dumps({'type': 'error', 'message': f'Generator error: {str(e)}'})}\n\n"
            except:
                # If even the error message fails, just end silently
                pass

    response = Response(generate(), mimetype='text/event-stream')
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['Connection'] = 'keep-alive'
    response.headers['X-Accel-Buffering'] = 'no'  # Disable Nginx buffering if present
    return response


@status_bp.route('/crawl/<session_id>/status-simple', methods=['GET'])
def crawl_status_polling(session_id):
    """
    Simple polling-based status endpoint (alternative to SSE).
    
    This endpoint provides a simple JSON response with current status,
    useful for environments where SSE doesn't work reliably.
    
    Args:
        session_id (str): The session ID to check
        
    Returns:
        JSON response with current status and recent messages
        
    Error Codes:
        404: Session not found
    """
    session = session_manager.get_session(session_id)
    
    if not session:
        return jsonify({"error": "Session not found"}), 404
    
    # Collect any pending messages (drain the queue)
    messages = []
    try:
        while True:
            message = session.messages.get_nowait()
            messages.append(message)
    except queue.Empty:
        pass
    
    # Check if cache is available
    cache_available = cache_service.is_available()
    
    # Prepare response with basic session info
    response = {
        "session_id": session_id,
        "status": session.status,
        "completed": session.completed,
        "error": session.error,
        "total_images": session.total_images,
        "total_pages": session.total_pages,
        "messages": messages,
        "image_stats": session.image_stats,
        "cache_available": cache_available,
        "skip_cache": session.skip_cache if hasattr(session, 'skip_cache') else False
    }
    
    # Add cache-specific information if available
    if hasattr(session, 'cache_hits') and session.cache_hits > 0:
        response["cache_hits"] = session.cache_hits
        
        # Add cache info to image stats if not already there
        if session.image_stats and "cache" not in session.image_stats and session.cache_hits > 0:
            response["image_stats"]["cache"] = {
                "hit": True,
                "cache_hits": session.cache_hits
            }
            

    
    # Add overall cache statistics if cache is available
    if cache_available:
        try:
            cache_stats = cache_service.metrics.get_performance_stats()
            if cache_stats:
                response["cache_statistics"] = {
                    'hit_rates': {
                        'html': cache_stats.get('html_cache', {}).get('hit_rate', 0),
                        'query': cache_stats.get('query_cache', {}).get('hit_rate', 0),
                        'embedding': cache_stats.get('embedding_cache', {}).get('hit_rate', 0)
                    },
                    'overall_hit_rate': cache_stats.get('overall', {}).get('overall_hit_rate', 0),
                    'total_hits': sum(c.get('total_hits', 0) for c in cache_stats.values() if isinstance(c, dict)),
                    'performance_gains': {
                        'html': '~85% faster',
                        'query': '~90% faster',
                        'embedding': '~70% faster'
                    }
                }
        except Exception:
            pass
    
    return jsonify(response) 