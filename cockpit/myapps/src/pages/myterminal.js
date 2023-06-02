import React from 'react';
import { useLocation } from 'react-router-dom';
import UserTerminal from "../lib/terminal";

const MyTerminal = (props): React$Element<React$FragmentType> => {
    const location = useLocation();
    const id = new URLSearchParams(location.search).get("id");

    return (
        <div className='ct-page-fill' id="terminal">
            {/* <UserTerminal runCmd={`docker exec -it ${id} bash\n`} /> */}
            <UserTerminal runCmd={`docker exec -it ${id} sh -c "if [ -x /bin/bash ]; then exec /bin/bash; else exec /bin/sh; fi" \n`} />
        </div>
    );
}

// const MyTerminal = (props): React$Element<React$FragmentType> => {
//     return (
//         <div className='ct-page-fill' id="terminal" >
//             <UserTerminal runCmd={`docker exec -it ${props.data.customer_name} bash\n`} />
//         </div>
//     );
// }
export default MyTerminal;
