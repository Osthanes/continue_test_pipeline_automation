# continue_test_pipeline
A continue test pipeline automation that it triggers a given JazzHub project pipeline. It checks the status of the job in each pipeline stages and validates if it executed successfully.

Mandatory input parameters:

1. Export 'ibmIdUsername' and 'ibmIdPassword'.

        'ibmIdUsername' is the IBM ID username needed to login onto jazzhub.

        'ibmIdPassword' is the IBM ID password needed to login onto jazzhub.

        Example:
                export ibmIdUsername=<IBM ID psername>
                export ibmIdPassword=<IBM ID password>

2. Set 'jazzHubHost' and 'jazzHubProjectName' in the pipeline_test.property file.

        'jazzHubHost' is the url to jazzhub and is needed when for example calling jazzhub to get jazzhub project information.

                #Prod:  jazzHubHost=https://hub.jazz.net

                #QA:    jazzHubHost=https://qa.hub.jazz.net

                #Beta3: jazzHubHost=https://beta3.hub.jazz.net 
                       
        'jazzHubProjectName' is the name of the most commonly used jazzhub project. It should format like that:

                'username | project name'

        Example for the 'Prod' target:
                [Config]
                jazzHubHost=https://hub.jazz.net
                jazzHubProjectName=<The jazzhub project>




